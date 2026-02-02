# signature_remover.py
# Odstranění elektronických podpisů z PDF
# Build 1.0 | © 2025 Ing. Martin Cieślar

import os
import sys
import subprocess
import shutil
import logging
from pathlib import Path
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)

# Zkusíme importovat pikepdf (preferované) nebo pypdf jako fallback
try:
    import pikepdf
    PIKEPDF_AVAILABLE = True
except ImportError:
    PIKEPDF_AVAILABLE = False
    logger.warning("pikepdf není nainstalován, zkouším pypdf")

try:
    from pypdf import PdfReader, PdfWriter
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False


def remove_signatures(input_path: str, output_path: Optional[str] = None) -> Tuple[bool, str]:
    """
    Odstraní všechny elektronické podpisy z PDF souboru.

    Args:
        input_path: Cesta ke vstupnímu PDF
        output_path: Cesta k výstupnímu PDF (pokud None, přidá _unsigned suffix)

    Returns:
        Tuple (success, message)
    """
    input_path = Path(input_path)

    if not input_path.exists():
        return False, f"Soubor neexistuje: {input_path}"

    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_unsigned{input_path.suffix}"
    else:
        output_path = Path(output_path)

    # Zkusíme použít Ghostscript pro odstranění podpisů (nejspolehlivější)
    gs_path = _find_ghostscript()
    if gs_path:
        result = _remove_signatures_ghostscript(input_path, output_path, gs_path)
        if result[0]:  # Pokud Ghostscript uspěl, použijeme to
            return result
    
    # Fallback na Python knihovny
    if PIKEPDF_AVAILABLE:
        return _remove_signatures_pikepdf(input_path, output_path)
    elif PYPDF_AVAILABLE:
        return _remove_signatures_pypdf(input_path, output_path)
    else:
        return False, "Není nainstalována žádná PDF knihovna (pikepdf nebo pypdf) a Ghostscript není dostupný"


def _find_ghostscript() -> Optional[str]:
    """Najde cestu k Ghostscript"""
    # Hledáme v distribuci aplikace (pro PyInstaller)
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
        for gs_name in ['gswin64c.exe', 'gswin32c.exe', 'gs.exe']:
            gs_path = os.path.join(base_path, gs_name)
            if os.path.isfile(gs_path):
                return gs_path
    
    # Standardní cesty Windows
    ghostscript_paths = [
        r"C:\Program Files\gs\gs10.02.1\bin\gswin64c.exe",
        r"C:\Program Files\gs\gs10.02.0\bin\gswin64c.exe",
        r"C:\Program Files\gs\gs10.01.2\bin\gswin64c.exe",
        r"C:\Program Files\gs\gs10.01.1\bin\gswin64c.exe",
        r"C:\Program Files\gs\gs10.00.0\bin\gswin64c.exe",
        r"C:\Program Files\gs\gs9.56.1\bin\gswin64c.exe",
        r"C:\Program Files (x86)\gs\gs10.02.1\bin\gswin32c.exe",
        r"C:\Program Files (x86)\gs\gs9.56.1\bin\gswin32c.exe",
    ]
    
    for path in ghostscript_paths:
        if os.path.isfile(path):
            return path
        gs_path = shutil.which(path)
        if gs_path:
            return gs_path
    
    return None


def _remove_signatures_ghostscript(input_path: Path, output_path: Path, gs_path: str) -> Tuple[bool, str]:
    """Odstranění podpisů pomocí Ghostscript (nejspolehlivější metoda)"""
    try:
        # Ghostscript převede PDF a automaticky odstraní podpisy
        cmd = [
            gs_path,
            "-dNOPAUSE",
            "-dBATCH",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.7",
            "-dPDFSETTINGS=/prepress",
            "-dAutoRotatePages=/None",
            "-sOutputFile=" + str(output_path),
            str(input_path)
        ]
        
        logger.info(f"Odstraňuji podpisy pomocí Ghostscript: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            return True, f"Podpisy odstraněny pomocí Ghostscript → {output_path.name}"
        else:
            error_msg = result.stderr or result.stdout or "Neznámá chyba"
            logger.error(f"Ghostscript chyba: {error_msg}")
            return False, f"Ghostscript selhal: {error_msg[:200]}"
    
    except subprocess.TimeoutExpired:
        return False, "Časový limit vypršel (5 minut)"
    except FileNotFoundError:
        return False, f"Ghostscript nenalezen: {gs_path}"
    except Exception as e:
        logger.exception(f"Chyba při odstraňování podpisů (Ghostscript): {e}")
        return False, f"Chyba: {str(e)}"


def _remove_signatures_pikepdf(input_path: Path, output_path: Path) -> Tuple[bool, str]:
    """Odstranění podpisů pomocí pikepdf - kompletní odstranění jako PDF24"""
    try:
        with pikepdf.open(input_path) as pdf:
            signatures_removed = 0

            # 1. Odstraníme podpisové anotace ze stránek
            for page_num, page in enumerate(pdf.pages):
                if '/Annots' in page:
                    annots = page['/Annots']
                    if not isinstance(annots, list):
                        annots = list(annots)
                    
                    new_annots = []
                    for annot_ref in annots:
                        try:
                            # Získáme objekt anotace
                            annot_obj = annot_ref
                            if hasattr(annot_ref, 'get_object'):
                                annot_obj = annot_ref.get_object()
                            
                            # Zkontrolujeme zda je to podpis
                            is_signature = False
                            
                            # Kontrola /Subtype
                            if '/Subtype' in annot_obj:
                                subtype = str(annot_obj['/Subtype'])
                                if subtype == '/Sig':
                                    is_signature = True
                                elif subtype == '/Widget':
                                    # Widget může být podpisové pole
                                    if '/FT' in annot_obj:
                                        ft = str(annot_obj['/FT'])
                                        if ft == '/Sig':
                                            is_signature = True
                            
                            # Kontrola /FT přímo
                            if not is_signature and '/FT' in annot_obj:
                                ft = str(annot_obj['/FT'])
                                if ft == '/Sig':
                                    is_signature = True
                            
                            if is_signature:
                                signatures_removed += 1
                                logger.debug(f"Odstraňuji podpis z anotace na stránce {page_num + 1}")
                            else:
                                new_annots.append(annot_ref)
                                
                        except Exception as e:
                            logger.warning(f"Chyba při zpracování anotace: {e}")
                            new_annots.append(annot_ref)
                    
                    # Aktualizujeme anotace
                    if len(new_annots) < len(annots):
                        if new_annots:
                            page['/Annots'] = new_annots
                        else:
                            # Pokud nejsou žádné anotace, odstraníme klíč
                            del page['/Annots']

            # 2. Odstraníme /AcroForm a podpisová pole
            if '/AcroForm' in pdf.Root:
                acroform = pdf.Root['/AcroForm']
                
                # Projdeme Fields a odstraníme podpisová pole
                if '/Fields' in acroform:
                    fields = acroform['/Fields']
                    if not isinstance(fields, list):
                        fields = list(fields)
                    
                    new_fields = []
                    for field_ref in fields:
                        try:
                            field_obj = field_ref
                            if hasattr(field_ref, 'get_object'):
                                field_obj = field_ref.get_object()
                            
                            # Zkontrolujeme zda je to podpisové pole
                            if '/FT' in field_obj:
                                ft = str(field_obj['/FT'])
                                if ft == '/Sig':
                                    signatures_removed += 1
                                    logger.debug("Odstraňuji podpisové pole z AcroForm")
                                    continue
                            
                            # Odstraníme /V (podpisová hodnota) pokud existuje
                            if '/V' in field_obj:
                                del field_obj['/V']
                            
                            new_fields.append(field_ref)
                        except Exception as e:
                            logger.warning(f"Chyba při zpracování pole: {e}")
                            new_fields.append(field_ref)
                    
                    # Aktualizujeme Fields
                    if len(new_fields) < len(fields):
                        if new_fields:
                            acroform['/Fields'] = new_fields
                        else:
                            # Pokud nejsou žádná pole, odstraníme klíč
                            del acroform['/Fields']
                
                # Odstraníme SigFlags
                if '/SigFlags' in acroform:
                    del acroform['/SigFlags']
                
                # Pokud je AcroForm prázdný, odstraníme ho
                if not acroform or (not '/Fields' in acroform or len(acroform.get('/Fields', [])) == 0):
                    del pdf.Root['/AcroForm']

            # 3. Odstraníme /DSS (Document Security Store) - obsahuje certifikáty
            if '/DSS' in pdf.Root:
                signatures_removed += 1
                del pdf.Root['/DSS']
                logger.debug("Odstraňuji Document Security Store (DSS)")

            # 4. Odstraníme všechny /Sig objekty z dokumentu
            # Projdeme všechny objekty v PDF
            sig_objects_removed = 0
            objects_to_remove = []
            
            for obj_num, obj in pdf.objects.items():
                try:
                    if hasattr(obj, 'get') and obj.get('/Type') == '/Sig':
                        objects_to_remove.append(obj_num)
                        sig_objects_removed += 1
                except:
                    pass
            
            # Odstraníme nalezené objekty
            for obj_num in objects_to_remove:
                try:
                    del pdf.objects[obj_num]
                except:
                    pass
            
            if sig_objects_removed > 0:
                signatures_removed += sig_objects_removed
                logger.debug(f"Odstraněno {sig_objects_removed} /Sig objektů")

            # Uložíme výsledek
            pdf.save(output_path)

            if signatures_removed > 0:
                return True, f"Odstraněno {signatures_removed} podpisů/podpisových objektů → {output_path.name}"
            else:
                return True, f"Žádné podpisy nenalezeny, soubor zkopírován → {output_path.name}"

    except Exception as e:
        logger.exception(f"Chyba při odstraňování podpisů (pikepdf): {e}")
        return False, f"Chyba: {str(e)}"


def _remove_signatures_pypdf(input_path: Path, output_path: Path) -> Tuple[bool, str]:
    """Odstranění podpisů pomocí pypdf (fallback) - kompletní odstranění"""
    try:
        reader = PdfReader(str(input_path))
        writer = PdfWriter()

        signatures_removed = 0

        # 1. Zkopírujeme celý dokument a pak upravíme stránky
        writer.clone_reader_document_root(reader)
        
        # 2. Projdeme všechny stránky a odstraníme podpisové anotace
        for page_num, page in enumerate(reader.pages):
            # Získáme objekt stránky z readeru
            page_obj = page.get_object()
            
            # Odstraníme podpisové anotace
            if '/Annots' in page_obj:
                annots = page_obj['/Annots']
                if not isinstance(annots, list):
                    annots = list(annots)
                
                new_annots = []
                for annot_ref in annots:
                    try:
                        annot_obj = annot_ref.get_object() if hasattr(annot_ref, 'get_object') else annot_ref
                        
                        # Zkontrolujeme zda je to podpis
                        is_signature = False
                        
                        # Kontrola /Subtype
                        if '/Subtype' in annot_obj:
                            subtype = annot_obj.get('/Subtype')
                            if subtype == '/Sig':
                                is_signature = True
                            elif subtype == '/Widget':
                                # Widget může být podpisové pole
                                if '/FT' in annot_obj:
                                    ft = annot_obj.get('/FT')
                                    if ft == '/Sig':
                                        is_signature = True
                        
                        # Kontrola /FT přímo
                        if not is_signature and '/FT' in annot_obj:
                            ft = annot_obj.get('/FT')
                            if ft == '/Sig':
                                is_signature = True
                        
                        if is_signature:
                            signatures_removed += 1
                            logger.debug(f"Odstraňuji podpis z anotace na stránce {page_num + 1}")
                        else:
                            new_annots.append(annot_ref)
                    except Exception as e:
                        logger.warning(f"Chyba při zpracování anotace: {e}")
                        new_annots.append(annot_ref)
                
                # Aktualizujeme anotace v objektu stránky
                if len(new_annots) < len(annots):
                    if new_annots:
                        page_obj['/Annots'] = new_annots
                    else:
                        del page_obj['/Annots']
            
            # Přidáme stránku do writeru
            writer.add_page(page)

        # 2. Odstraníme AcroForm a podpisová pole z root objektu
        # pypdf má omezený přístup, ale zkusíme to přes writer metadata
        try:
            # Zkusíme přistupovat k root objektu přes reader
            if hasattr(reader, 'trailer') and reader.trailer:
                root_ref = reader.trailer.get('/Root')
                if root_ref:
                    root = root_ref.get_object() if hasattr(root_ref, 'get_object') else root_ref
                    
                    if '/AcroForm' in root:
                        acroform_ref = root['/AcroForm']
                        acroform = acroform_ref.get_object() if hasattr(acroform_ref, 'get_object') else acroform_ref
                        
                        # Projdeme Fields a odstraníme podpisová pole
                        if '/Fields' in acroform:
                            fields = acroform['/Fields']
                            if not isinstance(fields, list):
                                fields = list(fields)
                            
                            new_fields = []
                            for field_ref in fields:
                                try:
                                    field_obj = field_ref.get_object() if hasattr(field_ref, 'get_object') else field_ref
                                    
                                    # Zkontrolujeme zda je to podpisové pole
                                    if '/FT' in field_obj:
                                        ft = field_obj.get('/FT')
                                        if ft == '/Sig':
                                            signatures_removed += 1
                                            logger.debug("Odstraňuji podpisové pole z AcroForm")
                                            continue
                                    
                                    # Odstraníme /V (podpisová hodnota) pokud existuje
                                    if '/V' in field_obj:
                                        del field_obj['/V']
                                    
                                    new_fields.append(field_ref)
                                except Exception as e:
                                    logger.warning(f"Chyba při zpracování pole: {e}")
                                    new_fields.append(field_ref)
                            
                            # Aktualizujeme Fields
                            if len(new_fields) < len(fields):
                                if new_fields:
                                    acroform['/Fields'] = new_fields
                                else:
                                    del acroform['/Fields']
                        
                        # Odstraníme SigFlags
                        if '/SigFlags' in acroform:
                            del acroform['/SigFlags']
                        
                        # Pokud je AcroForm prázdný, odstraníme ho
                        if not '/Fields' in acroform or len(acroform.get('/Fields', [])) == 0:
                            del root['/AcroForm']

                    # 3. Odstraníme /DSS (Document Security Store) - obsahuje certifikáty
                    if '/DSS' in root:
                        signatures_removed += 1
                        del root['/DSS']
                        logger.debug("Odstraňuji Document Security Store (DSS)")
        except Exception as e:
            logger.warning(f"Chyba při odstraňování AcroForm/DSS: {e}")
            # Pokračujeme dál - hlavní je odstranit anotace ze stránek

        # 4. Projdeme všechny objekty a odstraníme /Sig objekty
        # pypdf nemá přímý přístup k všem objektům jako pikepdf, ale můžeme zkusit
        # projít přes metadata a další struktury
        
        # Uložíme výsledek
        with open(output_path, 'wb') as f:
            writer.write(f)

        if signatures_removed > 0:
            return True, f"Odstraněno {signatures_removed} podpisů/podpisových objektů → {output_path.name}"
        else:
            return True, f"Žádné podpisy nenalezeny, soubor zkopírován → {output_path.name}"

    except Exception as e:
        logger.exception(f"Chyba při odstraňování podpisů (pypdf): {e}")
        return False, f"Chyba: {str(e)}"


def remove_signatures_batch(input_files: List[str], output_dir: Optional[str] = None) -> List[Tuple[str, bool, str]]:
    """
    Dávkové odstranění podpisů z více PDF souborů.

    Args:
        input_files: Seznam cest k PDF souborům
        output_dir: Výstupní složka (pokud None, použije se stejná složka s _unsigned suffixem)

    Returns:
        Seznam výsledků: [(filename, success, message), ...]
    """
    results = []

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    for input_path in input_files:
        input_path = Path(input_path)

        if output_dir:
            output_path = output_dir / f"{input_path.stem}_unsigned{input_path.suffix}"
        else:
            output_path = None  # remove_signatures vytvoří vlastní

        success, message = remove_signatures(str(input_path), str(output_path) if output_path else None)
        results.append((input_path.name, success, message))

    return results


# Test
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Použití: python signature_remover.py <input.pdf> [output.pdf]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    success, message = remove_signatures(input_file, output_file)
    print(f"{'✓' if success else '✗'} {message}")
