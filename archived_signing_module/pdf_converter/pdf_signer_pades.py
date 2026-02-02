# pdf_signer_pades.py
# PAdES PDF Signer with Hardware Token Support
# Supports PKCS#11 tokens (iSignum/PostSignum) and Windows Certificate Store
# Build 3.0 | © 2025 Ing. Martin Cieślar

import os
import sys
import logging
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# PAdES and PDF signing libraries
try:
    from pyhanko.sign import signers, fields
    from pyhanko.sign.fields import SigFieldSpec
    from pyhanko.sign.general import SigningError
    from pyhanko.sign.signers.pdf_signer import PdfSignatureMetadata
    PYHANKO_AVAILABLE = True
except ImportError:
    PYHANKO_AVAILABLE = False
    logger.warning("pyhanko není nainstalován - PAdES podepisování nebude fungovat")

# PKCS#11 support
PKCS11_AVAILABLE = False
try:
    from pyhanko.keys.pkcs11 import PKCS11SigningContext
    PKCS11_AVAILABLE = True
except ImportError:
    try:
        from pkcs11 import lib, ObjectClass, Attribute
        PKCS11_AVAILABLE = True
        logger.info("PKCS#11 podpora dostupná přes python-pkcs11")
    except ImportError:
        PKCS11_AVAILABLE = False
        logger.warning("PKCS#11 podpora není dostupná")

# Windows Certificate Store (CAPI/CNG)
WINDOWS_CERT_STORE_AVAILABLE = False
try:
    if sys.platform == 'win32':
        try:
            import win32crypt
            import win32security
            WINDOWS_CERT_STORE_AVAILABLE = True
        except ImportError:
            # Alternativní způsob pomocí cryptography a certifi
            try:
                from cryptography.hazmat.backends import default_backend
                from cryptography import x509
                import ssl
                import socket
                WINDOWS_CERT_STORE_AVAILABLE = True
                logger.info("Windows Certificate Store podpora dostupná přes cryptography")
            except:
                pass
except:
    pass


@dataclass
class SignerConfig:
    """Konfigurace pro podepisování"""
    # TSA (Time Stamping Authority)
    tsa_url: str = "http://tsa.postsignum.cz/tsp"
    tsa_enabled: bool = True
    
    # PKCS#11 knihovny
    pkcs11_libraries: Dict[str, List[str]] = None
    
    # Výchozí nastavení podpisu
    hash_algorithm: str = "SHA-256"
    signature_mechanism: str = "RSA_PKCS1v15"
    
    # PAdES nastavení
    pades_level: str = "PAdES-B-LT"  # PAdES-B, PAdES-B-LT, PAdES-B-LTA
    
    def __post_init__(self):
        if self.pkcs11_libraries is None:
            self.pkcs11_libraries = {
                'isignum': [
                    r"C:\Program Files\iSignum\pkcs11.dll",
                    r"C:\Program Files (x86)\iSignum\pkcs11.dll",
                ],
                'postsignum': [
                    r"C:\Program Files\PostSignum\pkcs11.dll",
                    r"C:\Program Files (x86)\PostSignum\pkcs11.dll",
                ],
                'bit4id': [
                    r"C:\Windows\System32\bit4xpki.dll",
                    r"C:\Program Files\BIT4ID\bit4xpki.dll",
                ],
                'safenet': [
                    r"C:\Windows\System32\eTPKCS11.dll",
                    r"C:\Program Files\SafeNet\Authentication\SAC\x64\eTPKCS11.dll",
                ],
            }


@dataclass
class VisualSignatureConfig:
    """Konfigurace pro vizuální podpis"""
    # Pozice a velikost
    x: float = 50.0
    y: float = 50.0
    width: float = 200.0
    height: float = 100.0
    page_number: int = 0  # 0 = první stránka
    
    # Obsah vizuálního podpisu
    show_name: bool = True
    show_organization: bool = True
    show_datetime: bool = True
    show_reason: bool = True
    show_location: bool = True
    
    # Vlastní logo/obrázek
    logo_path: Optional[str] = None
    logo_position: str = "left"  # left, right, top, bottom
    
    # Styl
    border_color: Tuple[int, int, int] = (0, 0, 0)  # RGB
    background_color: Tuple[int, int, int] = (255, 255, 255)  # RGB
    text_color: Tuple[int, int, int] = (0, 0, 0)  # RGB
    font_size: int = 10


@dataclass
class SigningOptions:
    """Nastavení pro podepisování PDF"""
    # Certifikát
    certificate_source: str = "pkcs11"  # "pkcs11", "windows_store", "pfx"
    certificate_path: Optional[str] = None  # Pro .pfx soubory
    pkcs11_lib: Optional[str] = None  # Cesta k PKCS#11 knihovně
    pkcs11_slot: int = 0
    pkcs11_pin: Optional[str] = None
    certificate_label: Optional[str] = None  # Label certifikátu na tokenu
    windows_store_location: str = "CurrentUser"  # CurrentUser, LocalMachine
    windows_store_name: str = "My"  # My, Trust, CA, etc.
    
    # Metadata podpisu
    reason: str = "Elektronický podpis"
    location: str = "Česká republika"
    contact_info: str = ""
    organization: str = "ČKAIT"  # Pro vizuální podpis
    
    # TSA
    use_tsa: bool = True
    tsa_url: Optional[str] = None  # Pokud None, použije se z config
    
    # Vizuální podpis
    visual_signature: bool = True
    visual_config: Optional[VisualSignatureConfig] = None
    
    # PAdES
    pades_level: str = "PAdES-B-LT"
    
    # Hash algoritmus
    hash_algorithm: str = "SHA-256"


def load_config(config_path: Optional[str] = None) -> SignerConfig:
    """
    Načte konfiguraci ze souboru nebo vrátí výchozí.
    
    Args:
        config_path: Cesta k konfiguračnímu souboru (JSON nebo YAML)
    
    Returns:
        SignerConfig objekt
    """
    if config_path and Path(config_path).exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.endswith('.yaml') or config_path.endswith('.yml'):
                    import yaml
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            
            return SignerConfig(**data)
        except Exception as e:
            logger.warning(f"Chyba při načítání konfigurace: {e}, použiji výchozí")
    
    return SignerConfig()


def save_config(config: SignerConfig, config_path: str):
    """Uloží konfiguraci do souboru"""
    try:
        data = {
            'tsa_url': config.tsa_url,
            'tsa_enabled': config.tsa_enabled,
            'pkcs11_libraries': config.pkcs11_libraries,
            'hash_algorithm': config.hash_algorithm,
            'signature_mechanism': config.signature_mechanism,
            'pades_level': config.pades_level,
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            if config_path.endswith('.yaml') or config_path.endswith('.yml'):
                import yaml
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            else:
                json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Chyba při ukládání konfigurace: {e}")


def find_pkcs11_library(config: SignerConfig, token_type: Optional[str] = None) -> Optional[str]:
    """
    Najde PKCS#11 knihovnu podle typu tokenu.
    
    Args:
        config: Konfigurace s cestami k knihovnám
        token_type: Typ tokenu (isignum, postsignum, bit4id, safenet)
    
    Returns:
        Cesta k PKCS#11 knihovně nebo None
    """
    if token_type and token_type.lower() in config.pkcs11_libraries:
        for path in config.pkcs11_libraries[token_type.lower()]:
            if os.path.isfile(path):
                logger.info(f"Nalezena PKCS#11 knihovna ({token_type}): {path}")
                return path
    
    # Automatická detekce - procházíme všechny typy
    for token_type_name, paths in config.pkcs11_libraries.items():
        for path in paths:
            if os.path.isfile(path):
                logger.info(f"Nalezena PKCS#11 knihovna ({token_type_name}): {path}")
                return path
    
    return None


def list_certificates_pkcs11(pkcs11_lib: str, pin: Optional[str] = None, slot_no: int = 0) -> List[Dict[str, Any]]:
    """
    Zobrazí seznam certifikátů z PKCS#11 tokenu.
    
    Args:
        pkcs11_lib: Cesta k PKCS#11 knihovně
        pin: PIN pro token
        slot_no: Číslo slotu
    
    Returns:
        Seznam certifikátů: [{"label": "...", "subject": "...", "issuer": "...", "serial": "...", "valid_from": "...", "valid_to": "..."}, ...]
    """
    if not PKCS11_AVAILABLE:
        return []
    
    certs = []
    try:
        # Použijeme pyhanko PKCS11SigningContext
        try:
            from pyhanko.keys.pkcs11 import PKCS11SigningContext
            with PKCS11SigningContext(pkcs11_lib, slot_no=slot_no, user_pin=pin) as ctx:
                for cert_label, cert_obj in ctx.list_certs():
                    try:
                        subject = cert_obj.subject.rfc4514_string() if hasattr(cert_obj.subject, 'rfc4514_string') else str(cert_obj.subject)
                        issuer = cert_obj.issuer.rfc4514_string() if hasattr(cert_obj.issuer, 'rfc4514_string') else str(cert_obj.issuer)
                        serial = hex(cert_obj.serial_number)[2:].upper() if hasattr(cert_obj, 'serial_number') else "N/A"
                        
                        certs.append({
                            "label": cert_label,
                            "subject": subject,
                            "issuer": issuer,
                            "serial": serial,
                            "source": "pkcs11",
                            "pkcs11_lib": pkcs11_lib,
                            "slot": slot_no
                        })
                    except Exception as e:
                        logger.warning(f"Chyba při načítání certifikátu {cert_label}: {e}")
        except ImportError:
            # Fallback na python-pkcs11
            from pkcs11 import lib, ObjectClass, Attribute
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend
            
            pkcs11_lib_obj = lib(pkcs11_lib)
            tokens = list(pkcs11_lib_obj.get_tokens())
            if tokens:
                token = tokens[slot_no] if slot_no < len(tokens) else tokens[0]
                with token.open(user_pin=pin) as session:
                    for obj in session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}):
                        try:
                            cert_data = bytes(obj[Attribute.VALUE])
                            cert = x509.load_der_x509_certificate(cert_data, default_backend())
                            
                            subject = cert.subject.rfc4514_string() if hasattr(cert.subject, 'rfc4514_string') else str(cert.subject)
                            issuer = cert.issuer.rfc4514_string() if hasattr(cert.issuer, 'rfc4514_string') else str(cert.issuer)
                            serial = hex(cert.serial_number)[2:].upper()
                            
                            label = None
                            try:
                                label_attr = obj.get(Attribute.LABEL)
                                if label_attr:
                                    label = label_attr.decode('utf-8', errors='ignore') if isinstance(label_attr, bytes) else str(label_attr)
                            except:
                                pass
                            
                            if not label:
                                try:
                                    cn = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
                                    label = cn
                                except:
                                    label = f"Cert_{serial[:8]}"
                            
                            certs.append({
                                "label": label,
                                "subject": subject,
                                "issuer": issuer,
                                "serial": serial,
                                "source": "pkcs11",
                                "pkcs11_lib": pkcs11_lib,
                                "slot": slot_no
                            })
                        except Exception as e:
                            logger.warning(f"Chyba při načítání certifikátu: {e}")
                            continue
    except Exception as e:
        logger.error(f"Chyba při načítání certifikátů z PKCS#11: {e}")
    
    return certs


def list_certificates_windows_store(location: str = "CurrentUser", store_name: str = "My") -> List[Dict[str, Any]]:
    """
    Zobrazí seznam certifikátů z Windows Certificate Store.
    
    Args:
        location: CurrentUser nebo LocalMachine
        store_name: Název úložiště (My, Trust, CA, etc.)
    
    Returns:
        Seznam certifikátů
    """
    if not WINDOWS_CERT_STORE_AVAILABLE:
        return []
    
    certs = []
    try:
        # Zkusíme použít win32crypt (pokud je dostupné)
        try:
            import win32crypt
            import win32security
            
            # Otevřeme úložiště certifikátů
            store_handle = win32crypt.CertOpenStore(
                win32crypt.CERT_STORE_PROV_SYSTEM,
                0,
                None,
                win32crypt.CERT_SYSTEM_STORE_CURRENT_USER if location == "CurrentUser" else win32crypt.CERT_SYSTEM_STORE_LOCAL_MACHINE,
                store_name
            )
            
            cert_context = win32crypt.CertEnumCertificatesInStore(store_handle, None)
            while cert_context:
                try:
                    subject = win32crypt.CertNameToStr(cert_context.dwCertEncodingType, cert_context.pCertInfo.Subject, win32crypt.CERT_SIMPLE_NAME_STR)
                    issuer = win32crypt.CertNameToStr(cert_context.dwCertEncodingType, cert_context.pCertInfo.Issuer, win32crypt.CERT_SIMPLE_NAME_STR)
                    
                    certs.append({
                        "label": subject,
                        "subject": subject,
                        "issuer": issuer,
                        "serial": hex(cert_context.pCertInfo.SerialNumber)[2:].upper(),
                        "source": "windows_store",
                        "store_location": location,
                        "store_name": store_name
                    })
                except Exception as e:
                    logger.warning(f"Chyba při načítání certifikátu z Windows Store: {e}")
                
                cert_context = win32crypt.CertEnumCertificatesInStore(store_handle, cert_context)
            
            win32crypt.CertCloseStore(store_handle, 0)
        except ImportError:
            # Fallback: použijeme PowerShell pro načtení certifikátů
            import subprocess
            try:
                ps_script = f'''
                Get-ChildItem -Path Cert:\\{location}\\{store_name} | ForEach-Object {{
                    [PSCustomObject]@{{
                        Subject = $_.Subject
                        Issuer = $_.Issuer
                        SerialNumber = $_.SerialNumber
                        Thumbprint = $_.Thumbprint
                    }}
                }} | ConvertTo-Json
                '''
                result = subprocess.run(
                    ["powershell", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='ignore',
                    timeout=10
                )
                if result.returncode == 0 and result.stdout:
                    import json
                    data = json.loads(result.stdout)
                    if isinstance(data, list):
                        for cert_data in data:
                            certs.append({
                                "label": cert_data.get('Subject', 'N/A'),
                                "subject": cert_data.get('Subject', 'N/A'),
                                "issuer": cert_data.get('Issuer', 'N/A'),
                                "serial": cert_data.get('SerialNumber', 'N/A'),
                                "source": "windows_store",
                                "store_location": location,
                                "store_name": store_name
                            })
            except Exception as e:
                logger.warning(f"Chyba při načítání certifikátů přes PowerShell: {e}")
    except Exception as e:
        logger.error(f"Chyba při načítání certifikátů z Windows Store: {e}")
    
    return certs


def list_all_certificates(config: SignerConfig) -> List[Dict[str, Any]]:
    """
    Zobrazí všechny dostupné certifikáty ze všech zdrojů.
    
    Args:
        config: Konfigurace
    
    Returns:
        Seznam všech dostupných certifikátů
    """
    all_certs = []
    
    # PKCS#11 certifikáty
    for token_type, paths in config.pkcs11_libraries.items():
        for path in paths:
            if os.path.isfile(path):
                try:
                    certs = list_certificates_pkcs11(path, pin=None, slot_no=0)
                    all_certs.extend(certs)
                    break  # Použijeme první nalezenou knihovnu pro daný typ
                except:
                    continue
    
    # Windows Certificate Store
    if WINDOWS_CERT_STORE_AVAILABLE:
        try:
            windows_certs = list_certificates_windows_store()
            all_certs.extend(windows_certs)
        except:
            pass
    
    return all_certs


def create_visual_signature_appearance(
    certificate,
    options: SigningOptions,
    visual_config: VisualSignatureConfig
) -> str:
    """
    Vytvoří text pro vizuální podpis podle PAdES standardu.
    
    Args:
        certificate: Certifikát
        options: Nastavení podepisování
        visual_config: Konfigurace vizuálního podpisu
    
    Returns:
        Text pro zobrazení podpisu
    """
    # Získáme jméno z certifikátu
    try:
        subject = certificate.subject
        cn = None
        for attr in subject:
            if hasattr(attr, 'oid') and hasattr(attr.oid, '_name') and attr.oid._name == 'commonName':
                cn = attr.value
                break
            elif hasattr(attr, 'rfc4514_string'):
                cn_str = attr.rfc4514_string()
                if 'CN=' in cn_str:
                    cn = cn_str.split('CN=')[1].split(',')[0].strip()
                    break
        
        name = cn or str(subject)
    except:
        name = "Elektronický podpis"
    
    # Vytvoříme text pro vizuální podpis
    lines = []
    
    if visual_config.show_name:
        lines.append(f"  {name}")
    
    if visual_config.show_organization and options.organization:
        lines.append(f"  {options.organization}")
    
    if visual_config.show_datetime:
        lines.append(f"  Datum: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    
    if visual_config.show_reason and options.reason:
        lines.append(f"  Důvod: {options.reason}")
    
    if visual_config.show_location and options.location:
        lines.append(f"  Lokace: {options.location}")
    
    return "\n".join(lines)


def sign_pdf_pades(
    input_path: str,
    output_path: Optional[str] = None,
    options: Optional[SigningOptions] = None,
    config: Optional[SignerConfig] = None
) -> Tuple[bool, str]:
    """
    Podepíše PDF podle PAdES standardu.
    
    Args:
        input_path: Cesta ke vstupnímu PDF
        output_path: Cesta k výstupnímu PDF (pokud None, přidá _signed suffix)
        options: Nastavení podepisování
        config: Konfigurace
    
    Returns:
        Tuple (success, message)
    """
    if not PYHANKO_AVAILABLE:
        return False, "pyhanko není nainstalován. Instalujte: pip install pyhanko pyhanko-certvalidator"
    
    if config is None:
        config = load_config()
    
    if options is None:
        options = SigningOptions()
    
    input_path = Path(input_path)
    if not input_path.exists():
        return False, f"Soubor neexistuje: {input_path}"
    
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_signed{input_path.suffix}"
    else:
        output_path = Path(output_path)
    
    try:
        # Vytvoříme signer podle zdroje certifikátu
        signer_obj = None
        certificate = None
        
        if options.certificate_source == "pkcs11":
            # PKCS#11 token
            if not options.pkcs11_lib:
                pkcs11_lib = find_pkcs11_library(config)
                if not pkcs11_lib:
                    return False, "PKCS#11 knihovna nenalezena. Zkontrolujte konfiguraci."
                options.pkcs11_lib = pkcs11_lib
            
            try:
                from pyhanko.keys.pkcs11 import PKCS11SigningContext
                with PKCS11SigningContext(
                    options.pkcs11_lib,
                    slot_no=options.pkcs11_slot,
                    user_pin=options.pkcs11_pin,
                    cert_label=options.certificate_label
                ) as signing_context:
                    signer_obj = signing_context
                    certificate = signing_context.cert
            except Exception as e:
                return False, f"Chyba při načítání certifikátu z PKCS#11: {str(e)}"
        
        elif options.certificate_source == "windows_store":
            # Windows Certificate Store
            return False, "Windows Certificate Store podpora bude implementována"
        
        elif options.certificate_source == "pfx":
            # .pfx soubor
            if not options.certificate_path:
                return False, "Cesta k .pfx souboru není zadána"
            
            from cryptography.hazmat.primitives.serialization import pkcs12
            from cryptography.hazmat.backends import default_backend
            from pyhanko.sign.signers.pdf_cms import SimpleSigner
            from pyhanko.keys import internal
            
            cert_path = Path(options.certificate_path)
            if not cert_path.exists():
                return False, f"Certifikát neexistuje: {cert_path}"
            
            pfx_password = options.pkcs11_pin.encode() if options.pkcs11_pin else None
            
            with open(cert_path, 'rb') as f:
                pfx_data = f.read()
            
            try:
                private_key, cert, additional_certs = pkcs12.load_key_and_certificates(
                    pfx_data,
                    pfx_password,
                    backend=default_backend()
                )
                if cert and private_key:
                    cert_obj = internal.translate_pyca_cryptography_cert_to_asn1(cert)
                    key_obj = internal.translate_pyca_cryptography_key_to_asn1(private_key)
                    cert_registry = [cert_obj]
                    if additional_certs:
                        for ac in additional_certs:
                            cert_registry.append(internal.translate_pyca_cryptography_cert_to_asn1(ac))
                    signer_obj = SimpleSigner(
                        signing_key=key_obj,
                        signing_cert=cert_obj,
                        cert_registry=cert_registry
                    )
                    certificate = cert
            except Exception as e:
                return False, f"Chyba při načítání .pfx souboru: {str(e)}"
        
        if not signer_obj or not certificate:
            return False, "Nepodařilo se načíst certifikát nebo privátní klíč"
        
        # Vytvoříme metadata podpisu
        try:
            cert_subject = certificate.subject
            signer_name = cert_subject.rfc4514_string() if hasattr(cert_subject, 'rfc4514_string') else str(cert_subject)
        except:
            signer_name = "Elektronický podpis"
        
        metadata = PdfSignatureMetadata(
            field_name="Signature1",
            reason=options.reason,
            location=options.location,
            contact_info=options.contact_info,
            signer_name=signer_name
        )
        
        # TSA (časové razítko)
        timestamp_url = None
        if options.use_tsa:
            timestamp_url = options.tsa_url or config.tsa_url
        
        # Vytvoříme PDF signer
        pdf_signer = signers.PdfSigner(
            signer_obj,
            signature_meta=metadata,
            timestamp_url=timestamp_url
        )
        
        # Vizuální podpis
        if options.visual_signature:
            visual_config = options.visual_config or VisualSignatureConfig()
            appearance_text = create_visual_signature_appearance(certificate, options, visual_config)
            
            pdf_signer.append_signature_field(
                SigFieldSpec(
                    "Signature1",
                    box=(visual_config.x, visual_config.y, 
                         visual_config.x + visual_config.width, 
                         visual_config.y + visual_config.height),
                    on_page=visual_config.page_number
                )
            )
        
        # Podepíšeme PDF
        with open(input_path, 'rb') as inf:
            with open(output_path, 'wb') as outf:
                pdf_signer.sign_pdf(inf, outf)
        
        return True, f"PDF podepsáno podle PAdES → {output_path.name}"
    
    except Exception as e:
        logger.exception(f"Chyba při podepisování PDF: {e}")
        return False, f"Chyba: {str(e)}"
