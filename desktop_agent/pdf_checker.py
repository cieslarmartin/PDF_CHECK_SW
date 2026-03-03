# pdf_checker.py
# PDF kontrolní funkce pro desktop agenta
# Převzato z PDF DokuCheck PRO v38

import re
import os
import hashlib
from datetime import datetime

try:
    from tsa_registry import is_tsa_issuer_qualified
except ImportError:
    def is_tsa_issuer_qualified(tsa_issuer):
        return False


def check_pdfa_version(content):
    """Zjistí verzi PDF/A"""
    try:
        patterns = [
            (rb"pdfaid:part=['\"]?3", 3),
            (rb'pdfaid:part>3<', 3),
            (rb"pdfaid:part=['\"]?2", 2),
            (rb'pdfaid:part>2<', 2),
            (rb"pdfaid:part=['\"]?1", 1),
            (rb'pdfaid:part>1<', 1),
        ]
        for pattern, version in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return version, 'OK' if version == 3 else 'FAIL'
        if b'PDF/A-3' in content: return 3, 'OK'
        if b'PDF/A-2' in content: return 2, 'FAIL'
        if b'PDF/A-1' in content: return 1, 'FAIL'
        return None, 'FAIL'
    except:
        return None, 'FAIL'


def _extract_tsa_issuer_from_pkcs7(pkcs7, tsa_oid):
    """Z PKCS7 (obsahující RFC3161 timestamp) vybere první CN za TSTInfo OID jako jméno TSA. Vrací řetězec nebo '—'.
    Pro TSA issuer se nepoužívá filtr ca_keywords – chceme zobrazit přesně název TSA (např. PostSignum TSA 4)."""
    try:
        idx = pkcs7.find(tsa_oid)
        if idx < 0:
            return '—'
        tail_hex = pkcs7[idx:].hex()
        found = []
        for typ in ['0c', '13', '1e']:
            for length in range(5, 80):
                hex_len = format(length, '02x')
                pattern = f'0603550403{typ}{hex_len}([0-9a-f]{{{length*2}}})'
                for m in re.finditer(pattern, tail_hex, re.I):
                    try:
                        raw = bytes.fromhex(m.group(1))
                        cn = raw.decode('utf-16-be', errors='ignore') if typ == '1e' else raw.decode('utf-8', errors='ignore')
                        if len(cn) > 2:
                            found.append((m.start(), cn))
                    except Exception:
                        pass
        if found:
            found.sort(key=lambda x: x[0])
            return found[0][1].strip() or '—'
    except Exception:
        pass
    return '—'


def extract_all_signatures(content):
    """
    Extrahuje VŠECHNY podpisy z PDF

    STRATEGIE (v40 - robustní):
    1. PRIMÁRNĚ čte jméno z CN v PKCS7 certifikátu (vždy obsahuje správné jméno)
    2. FALLBACK na /Name pouze pokud CN nenajde platné jméno
    3. Filtruje systémové hodnoty (CA, TSA, OCSP, atd.)
    """
    signatures = []

    byteranges = list(re.finditer(rb'/ByteRange\s*\[([^\]]+)\]', content))

    # Klíčová slova pro filtrování systémových/CA certifikátů
    CA_KEYWORDS = [
        'postsignum', 'root', 'qca', 'tsa', 'tsu', 'ocsp', 'acaeid',
        'qualified ca', 'i.ca', 'eidentity', 'issř', 'aca ', 'certificate'
    ]

    # Špatné /Name hodnoty z CAD software (AutoCAD, Bluebeam, atd.)
    BAD_NAME_VALUES = [
        'cfg_0', 'default', 'auto', 'a_patt', 'not specified', 'format',
        'x_shbd', '_vykres', 'is_slaboproud', 'ep_x_legenda'
    ]

    for i, br in enumerate(byteranges):
        sig_info = {
            'index': i + 1,
            'signer': '—',
            'ckait': '—',
            'tsa': 'NONE',
            'tsa_issuer': '—',
            'date': '—',
            'valid': False,
            'signature_type': None
        }

        br_pos = br.start()
        search_start = max(0, br_pos - 25000)
        search_end = min(len(content), br_pos + 50000)
        search_area = content[search_start:search_end]

        # /M (datum) - načti vždy
        m_match = re.search(rb'/M\s*\(D:(\d{14})', search_area)
        if m_match:
            d = m_match.group(1).decode('ascii')
            sig_info['date'] = f"{d[:4]}-{d[4:6]}-{d[6:8]} {d[8:10]}:{d[10:12]}"

        # /Contents<hex> - PKCS7 data - PRIMÁRNÍ ZDROJ PRO JMÉNO
        contents_match = re.search(rb'/Contents\s*<([0-9a-fA-F]+)>', search_area)
        if contents_match:
            try:
                hex_data = contents_match.group(1).decode('ascii')
                pkcs7 = bytes.fromhex(hex_data)
                pkcs7_hex = pkcs7.hex()

                # TSA OID
                tsa_oid = bytes.fromhex('060b2a864886f70d010910020e')
                if tsa_oid in pkcs7:
                    sig_info['tsa'] = 'TSA'
                    sig_info['timestamp_valid'] = True
                    sig_info['tsa_issuer'] = _extract_tsa_issuer_from_pkcs7(pkcs7, tsa_oid)
                elif m_match:
                    sig_info['tsa'] = 'LOCAL'
                    sig_info['timestamp_valid'] = False

                # === ČKAIT/ČKA z OU (Organizational Unit) ===
                for length, sig_type in [(7, 'ČKAIT'), (6, 'ČKAIT'), (5, 'ČKA'), (4, 'ČKA')]:
                    if sig_info['ckait'] != '—':
                        break
                    hex_len = format(length, '02x')
                    ou_pattern = f'060355040b(?:0c|13){hex_len}([0-9a-f]{{{length*2}}})'
                    ou_match = re.search(ou_pattern, pkcs7_hex, re.I)
                    if ou_match:
                        try:
                            value = bytes.fromhex(ou_match.group(1)).decode('utf-8', errors='ignore')
                            if re.match(rf'^\d{{{length}}}$', value):
                                sig_info['ckait'] = value
                                sig_info['signature_type'] = sig_type
                        except:
                            pass

                # === JMÉNO Z CN (Common Name) ===
                found_cns = []
                for typ in ['0c', '13', '1e']:
                    for length in range(5, 80):
                        hex_len = format(length, '02x')
                        pattern = f'0603550403{typ}{hex_len}([0-9a-f]{{{length*2}}})'
                        for cn_match in re.finditer(pattern, pkcs7_hex, re.I):
                            try:
                                raw_bytes = bytes.fromhex(cn_match.group(1))
                                if typ == '1e':
                                    cn = raw_bytes.decode('utf-16-be', errors='ignore')
                                else:
                                    cn = raw_bytes.decode('utf-8', errors='ignore')
                                if len(cn) > 3:
                                    is_ca = any(kw in cn.lower() for kw in CA_KEYWORDS)
                                    has_space = ' ' in cn
                                    found_cns.append({
                                        'name': cn,
                                        'is_ca': is_ca,
                                        'has_space': has_space,
                                        'position': cn_match.start(),
                                        'type': typ
                                    })
                            except:
                                pass
                best_cn = None
                for cn_info in sorted(found_cns, key=lambda x: (x['is_ca'], not x['has_space'], x['position'])):
                    if not cn_info['is_ca']:
                        best_cn = cn_info['name']
                        break
                if best_cn:
                    sig_info['signer'] = best_cn
            except:
                pass

        # FALLBACK: /Name
        if sig_info['signer'] == '—':
            all_names = list(re.finditer(rb'/Name\s*\(([^)]*)\)', search_area))
            best_name = None
            best_score = -100
            for name_match in all_names:
                raw_name = name_match.group(1)
                if raw_name.startswith(b'\xfe\xff'):
                    decoded = raw_name[2:].decode('utf-16-be', errors='ignore')
                    is_utf16 = True
                elif b'\x00' in raw_name[:10]:
                    decoded = raw_name.decode('utf-16-be', errors='ignore')
                    is_utf16 = True
                else:
                    decoded = None
                    for enc in ['utf-8', 'windows-1250', 'latin-1']:
                        try:
                            decoded = raw_name.decode(enc)
                            break
                        except:
                            continue
                    is_utf16 = False
                if not decoded:
                    continue
                decoded = decoded.replace('\n', '').replace('\r', '').strip()
                if decoded.lower() in BAD_NAME_VALUES or len(decoded) < 4:
                    continue
                if '|' in decoded or decoded.startswith('ref_') or decoded.isdigit():
                    continue
                score = 0
                if is_utf16:
                    score += 20
                if ' ' in decoded:
                    score += 15
                if re.match(r'^(Ing\.|Mgr\.|Bc\.|Dr\.|akad\.|arch\.|MUDr\.|JUDr\.)', decoded):
                    score += 10
                score += min(len(decoded), 30) / 5
                score -= abs(name_match.start()) / 10000
                if score > best_score:
                    best_score = score
                    best_name = decoded
            if best_name:
                sig_info['signer'] = best_name

        sig_info['valid'] = (sig_info['signer'] != '—' and sig_info['ckait'] != '—')
        sig_info['certificate_valid'] = sig_info['valid']
        signatures.append(sig_info)
    return signatures


def check_signature_data(content):
    """Extrahuje informace o podpisech"""
    result = {
        'has_signature': False,
        'signer_name': '—',
        'ckait_number': '—',
        'signatures': [],
        'sig_count': 0
    }
    try:
        if b'/Type /Sig' not in content and b'/Type/Sig' not in content:
            return result
        result['has_signature'] = True
        signatures = extract_all_signatures(content)
        result['signatures'] = signatures
        result['sig_count'] = len(signatures)
        signers = list(dict.fromkeys([s['signer'] for s in signatures if s['signer'] != '—']))
        ckaits = list(dict.fromkeys([s['ckait'] for s in signatures if s['ckait'] != '—']))
        result['signer_name'] = ', '.join(signers) if signers else '—'
        result['ckait_number'] = ', '.join(ckaits) if ckaits else '—'
        return result
    except:
        return result


def check_timestamp(content):
    """Kontrola časového razítka"""
    try:
        if b'/Type /Sig' not in content and b'/Type/Sig' not in content:
            return 'NONE'
        signatures = extract_all_signatures(content)
        if not signatures:
            return 'NONE'
        tsas = [s['tsa'] for s in signatures]
        if all(t == 'TSA' for t in tsas):
            return 'TSA'
        elif any(t == 'TSA' for t in tsas):
            return 'PARTIAL'
        elif any(t == 'LOCAL' for t in tsas):
            return 'LOCAL'
        return 'NONE'
    except:
        return 'NONE'


def get_file_hash(filepath):
    """Vypočítá SHA256 hash souboru"""
    sha256 = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except:
        return None


def _resolve_obj(obj, reader):
    """Rozbalí indirect reference na reálný objekt (pypdf)."""
    if obj is None:
        return None
    try:
        if hasattr(obj, 'get_object'):
            return obj.get_object()
        if hasattr(reader, 'get_object') and hasattr(obj, 'indirect_reference'):
            return reader.get_object(obj.indirect_reference)
    except Exception:
        pass
    return obj


def is_pdf_locked_for_issr(reader):
    """
    Hloubková inspekce: zjistí, zda je PDF zamčeno pro ISSŘ (DocMDP Level 1).
    Kontroluje: 1) /Root/Perms/DocMDP, 2) /AcroForm/Fields /Sig: /Lock a /V -> /Reference -> /TransformParams.
    """
    try:
        catalog = reader.trailer.get("/Root") or getattr(reader, "root_object", None)
        if catalog is None:
            return False
        catalog = _resolve_obj(catalog, reader)
        if not catalog:
            return False

        # 1) Root check: /Perms/DocMDP – některá PDF definují zámek jen zde
        if "/Perms" in catalog:
            perms = _resolve_obj(catalog["/Perms"], reader)
            if perms and "/DocMDP" in perms:
                docmdp_ref = _resolve_obj(perms["/DocMDP"], reader)
                if docmdp_ref is not None:
                    params = docmdp_ref.get("/TransformParams")
                    if params is not None:
                        params = _resolve_obj(params, reader)
                        try:
                            if params is not None and params.get("/P") is not None and int(params.get("/P")) == 1:
                                return True
                        except (TypeError, ValueError):
                            pass
                    try:
                        if docmdp_ref.get("/P") is not None and int(docmdp_ref.get("/P")) == 1:
                            return True
                    except (TypeError, ValueError):
                        pass

        if "/AcroForm" not in catalog:
            return False
        acro = catalog["/AcroForm"]
        acro = _resolve_obj(acro, reader)
        if not acro or "/Fields" not in acro:
            return False
        fields = acro["/Fields"] or []
        for f_ref in fields:
            f = _resolve_obj(f_ref, reader)
            ft = f.get("/FT")
            if not f or (str(ft) if ft is not None else "") != "/Sig":
                continue
            # Přímý zámek pole
            lock = f.get("/Lock")
            if lock is not None:
                lock = _resolve_obj(lock, reader)
            if lock is not None:
                try:
                    p = lock.get("/P")
                    if p is not None and int(p) == 1:
                        return True
                except (TypeError, ValueError):
                    pass
            # TransformParams v referencích podpisu (/V -> /Reference -> /TransformParams)
            v = f.get("/V")
            if v is None:
                continue
            v_dict = _resolve_obj(v, reader)
            if not v_dict or "/Reference" not in v_dict:
                continue
            refs = v_dict.get("/Reference") or []
            for r_ref in refs:
                r_obj = _resolve_obj(r_ref, reader)
                if not r_obj:
                    continue
                tp = r_obj.get("/TransformParams")
                if tp is None:
                    continue
                params = _resolve_obj(tp, reader)
                try:
                    if params is not None and params.get("/P") is not None and int(params.get("/P")) == 1:
                        return True
                except (TypeError, ValueError):
                    pass
        return False
    except Exception:
        return False


def detect_docmdp_lock_via_reader(reader):
    """
    Detekce DocMDP přes strukturu PDF (AcroForm / Sig / Lock, TransformParams).
    Vrací {'locked': bool, 'level': int|None}. Použít preferenčně před byte-scanem.
    """
    try:
        if is_pdf_locked_for_issr(reader):
            return {'locked': True, 'level': 1}
        return {'locked': False, 'level': None}
    except Exception:
        return {'locked': False, 'level': None}


def detect_docmdp_lock(content):
    """
    Byte-scan fallback: prohledá min. 10 kB od každého výskytu /DocMDP.
    Vrací {'locked': bool, 'level': int|None}. Level 1 = nekompatibilní s ISSŘ.
    """
    try:
        if not content or b'/DocMDP' not in content:
            return {'locked': False, 'level': None}
        window_size = 10 * 1024  # 10 kB od každého /DocMDP
        start = 0
        while True:
            idx = content.find(b'/DocMDP', start)
            if idx < 0:
                break
            window = content[idx:idx + window_size]
            m1 = re.search(rb'/P\s+1(?:\s|>|\))', window)
            m2 = re.search(rb'/P\s+2(?:\s|>|\))', window)
            m3 = re.search(rb'/P\s+3(?:\s|>|\))', window)
            if m1 and (not m2 or m1.start() < m2.start()) and (not m3 or m1.start() < m3.start()):
                return {'locked': True, 'level': 1}
            if m2:
                return {'locked': False, 'level': 2}
            if m3:
                return {'locked': False, 'level': 3}
            start = idx + 1
        return {'locked': False, 'level': None}
    except Exception:
        return {'locked': False, 'level': None}


def analyze_pdf(content):
    """Kompletní analýza PDF"""
    pdfa_version, pdfa_status = check_pdfa_version(content)
    sig_data = check_signature_data(content)
    tsa = check_timestamp(content)
    docmdp = detect_docmdp_lock(content)
    if sig_data['has_signature']:
        if sig_data['sig_count'] > 0:
            all_have_ckait = all(s['ckait'] != '—' for s in sig_data['signatures'])
            all_have_name = all(s['signer'] != '—' for s in sig_data['signatures'])
            sig_status = 'OK' if (all_have_ckait and all_have_name) else 'PARTIAL'
        else:
            sig_status = 'PARTIAL'
    else:
        sig_status = 'FAIL'
    return {
        'pdfaVersion': pdfa_version,
        'pdfaStatus': pdfa_status,
        'sig': sig_status,
        'signer': sig_data['signer_name'],
        'ckait': sig_data['ckait_number'],
        'tsa': tsa,
        'sig_count': sig_data.get('sig_count', 0),
        'signatures': sig_data.get('signatures', []),
        'docmdp_level': docmdp['level'],
        'issr_compatible': not docmdp['locked'],
    }


def analyze_pdf_file(filepath):
    """Analýza PDF souboru z disku - vrací kompletní výsledky pro API. Kvalifikace TSA z lokálního whitelistu."""
    try:
        file_size = os.path.getsize(filepath)
        filename = os.path.basename(filepath)
        file_hash = get_file_hash(filepath)
        with open(filepath, 'rb') as f:
            if file_size <= 2 * 1024 * 1024:
                content = f.read()
            else:
                content = f.read(150 * 1024)
                f.seek(-1024 * 1024, 2)
                content += f.read()
        analysis = analyze_pdf(content)
        # Preferenční detekce DocMDP přes strukturu PDF (AcroForm / Sig / Lock, TransformParams)
        try:
            from pypdf import PdfReader
            reader = PdfReader(filepath)
            docmdp_reader = detect_docmdp_lock_via_reader(reader)
            analysis['docmdp_level'] = docmdp_reader['level']
            analysis['issr_compatible'] = not docmdp_reader['locked']
        except Exception:
            pass
        pdf_format = {
            'is_pdf_a3': analysis['pdfaVersion'] == 3,
            'exact_version': f"PDF/A-{analysis['pdfaVersion']}" if analysis['pdfaVersion'] else "PDF (ne PDF/A)",
            'standard': "ISO 19005-3:2012" if analysis['pdfaVersion'] == 3 else None
        }
        signatures = []
        for sig in analysis.get('signatures', []):
            tsa_issuer = sig.get('tsa_issuer', '—')
            tsa_qualified = is_tsa_issuer_qualified(tsa_issuer) if tsa_issuer and tsa_issuer != '—' else False
            signatures.append({
                'valid': sig.get('valid', False),
                'name': sig.get('signer', '—'),
                'ckait_number': sig.get('ckait', '—'),
                'signature_type': sig.get('signature_type', None),
                'timestamp_valid': sig.get('timestamp_valid', False),
                'certificate_valid': sig.get('certificate_valid', False),
                'date': sig.get('date', '—'),
                'tsa_issuer': tsa_issuer,
                'tsa_qualified': tsa_qualified,
            })
        docmdp_level = analysis.get('docmdp_level')
        issr_compatible = analysis.get('issr_compatible', True)
        return {
            'success': True,
            'file_name': filename,
            'file_hash': file_hash,
            'file_size': file_size,
            'processed_at': datetime.now().isoformat(),
            'results': {
                'pdf_format': pdf_format,
                'signatures': signatures,
                'file_info': {'filename': filename, 'size': file_size, 'hash': file_hash},
                'docmdp_level': docmdp_level,
                'issr_compatible': issr_compatible,
            },
            'display': {
                'pdf_version': pdf_format['exact_version'],
                'is_pdf_a3': pdf_format['is_pdf_a3'],
                'signature_count': len(signatures),
                'signatures': signatures,
                'docmdp_level': docmdp_level,
                'issr_compatible': issr_compatible,
            }
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'file_name': os.path.basename(filepath) if filepath else 'unknown'
        }


def find_all_pdfs(folder_path):
    """Najde všechny PDF soubory ve složce a podsložkách"""
    pdf_files = []
    try:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, folder_path).replace('\\', '/')
                    folder = os.path.dirname(rel_path).replace('\\', '/') or '.'
                    pdf_files.append({
                        'full_path': full_path,
                        'relative_path': rel_path,
                        'folder': folder,
                        'filename': file
                    })
    except Exception as e:
        print(f"Chyba při hledání PDF: {e}")
    return pdf_files


def analyze_multiple_pdfs(file_paths, progress_callback=None):
    """Analyzuje více PDF souborů najednou. Kvalifikace TSA z lokálního whitelistu."""
    results = []
    total = len(file_paths)
    for i, filepath in enumerate(file_paths, 1):
        try:
            if progress_callback:
                progress_callback(i, total, os.path.basename(filepath))
            result = analyze_pdf_file(filepath)
            results.append(result)
        except Exception as e:
            results.append({
                'success': False,
                'error': str(e),
                'file_name': os.path.basename(filepath)
            })
    return results


def analyze_folder(folder_path, progress_callback=None):
    """Analyzuje všechny PDF ve složce (rekurzivně). Kvalifikace TSA z lokálního whitelistu."""
    pdf_files = find_all_pdfs(folder_path)
    if not pdf_files:
        return {
            'folder_path': folder_path,
            'total_files': 0,
            'results': [],
            'error': 'Ve složce nebyly nalezeny žádné PDF soubory'
        }
    file_paths = [pdf['full_path'] for pdf in pdf_files]
    results = analyze_multiple_pdfs(file_paths, progress_callback)
    for i, result in enumerate(results):
        if i < len(pdf_files):
            result['folder'] = pdf_files[i]['folder']
            result['relative_path'] = pdf_files[i]['relative_path']
    return {
        'folder_path': folder_path,
        'total_files': len(pdf_files),
        'results': results
    }
