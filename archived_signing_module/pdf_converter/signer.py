# signer.py
# Elektronické podepisování PDF s PostSignum certifikátem
# Build 2.0 | © 2025 Ing. Martin Cieślar

import os
import sys
import io
import logging
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# POVINNÉ: pyhanko musí být nainstalován
try:
    from pyhanko.sign import signers, fields
    from pyhanko.sign.fields import SigFieldSpec
    from pyhanko.sign.general import SigningError
    PYHANKO_AVAILABLE = True
except ImportError as e:
    PYHANKO_AVAILABLE = False
    raise ImportError(
        "pyhanko není nainstalován! Podepisování vyžaduje pyhanko.\n"
        "Instalujte: pip install pyhanko pyhanko-certvalidator"
    ) from e

# PKCS#11 podpora pro hardware tokeny (BIT4ID, SafeNet, Gemalto, I.CA)
PKCS11_AVAILABLE = False
PKCS11SigningContext = None

# Zkusíme importovat pyhanko PKCS11 (pokud je dostupné)
try:
    from pyhanko.keys.pkcs11 import PKCS11SigningContext
    PKCS11_AVAILABLE = True
except ImportError:
    # Zkusíme python-pkcs11 přímo
    try:
        from pkcs11 import lib, Token, Mechanism
        PKCS11_AVAILABLE = True
        logger.info("PKCS#11 podpora dostupná přes python-pkcs11")
    except ImportError:
        PKCS11_AVAILABLE = False
        logger.warning("PKCS#11 podpora není dostupná - hardware tokeny nebudou fungovat. Instalujte: pip install python-pkcs11")


@dataclass
class SigningOptions:
    """Nastavení pro podepisování"""
    certificate_path: Optional[str] = None      # Cesta k .pfx/.p12 souboru (volitelné)
    pkcs11_lib: Optional[str] = None            # Cesta k PKCS#11 knihovně (pro token)
    token_pin: Optional[str] = None              # PIN pro token
    certificate_label: Optional[str] = None     # Label certifikátu na tokenu
    signature_type: str = "podpis"              # Typ: "podpis" nebo "razitko" (autorizační razítko)
    reason: str = "Elektronický podpis"          # Důvod podpisu
    location: str = "Česká republika"            # Lokace podpisu
    contact_info: str = ""                       # Kontaktní informace
    use_tsa: bool = False                        # Použít TSA (časové razítko) - výchozí: vypnuto
    tsa_url: str = "http://tsa.postsignum.cz/tsp"  # PostSignum TSA URL
    tsa_username: Optional[str] = None           # TSA HTTP Basic Auth uživatelské jméno
    tsa_password: Optional[str] = None           # TSA HTTP Basic Auth heslo
    visual_signature: bool = True                # Přidat vizuální podpis (čárové razítko)
    signature_field_name: str = "Signature1"    # Název podpisového pole
    signature_position: tuple = (50, 50, 200, 100)  # Pozice podpisu (x0, y0, x1, y1), pokud (-1, -1, -1, -1) = auto (pravý dolní roh)
    page_number: int = -1                        # Číslo stránky (-1 = poslední stránka, 0 = první stránka)
    verified_signer: Optional[Any] = None       # Předověřený signer objekt (pro batch processing)
    certificate_info: Optional[Dict[str, Any]] = None  # Informace o certifikátu (CN, expiration)


def find_pkcs11_library(token_type: Optional[str] = None) -> Optional[str]:
    """
    Najde PKCS#11 knihovnu pro různé typy tokenů používaných v ČR.
    
    Podporované tokeny:
    - SafeNet eToken (Thales)
    - BIT4ID
    - Gemalto IDGo
    - I.CA tokeny
    - Obecné PKCS#11 knihovny
    
    Args:
        token_type: Typ tokenu ('safenet', 'bit4id', 'gemalto', 'ica', None = automatická detekce)
    
    Returns:
        Tuple (cesta k PKCS#11 knihovně, typ tokenu) nebo (None, None)
    """
    # Seznam všech možných PKCS#11 knihoven používaných v ČR
    pkcs11_libraries = {
        'safenet': [
            r"C:\Program Files\SafeNet\Authentication\SAC\x64\eTPKCS11.dll",
            r"C:\Program Files (x86)\SafeNet\Authentication\SAC\x86\eTPKCS11.dll",
            r"C:\Program Files\SafeNet\Authentication\SAC\eTPKCS11.dll",
            r"C:\Program Files\Thales\Authentication\SAC\x64\eTPKCS11.dll",
            r"C:\Program Files (x86)\Thales\Authentication\SAC\x86\eTPKCS11.dll",
            r"C:\Windows\System32\eTPKCS11.dll",
            r"C:\Windows\SysWOW64\eTPKCS11.dll",
        ],
        'bit4id': [
            r"C:\Program Files\BIT4ID\eToken\pkcs11\bit4xpki.dll",
            r"C:\Program Files (x86)\BIT4ID\eToken\pkcs11\bit4xpki.dll",
            r"C:\Program Files\BIT4ID\eToken\pkcs11\x64\bit4xpki.dll",
            r"C:\Program Files (x86)\BIT4ID\eToken\pkcs11\x86\bit4xpki.dll",
            r"C:\Windows\System32\bit4xpki.dll",
            r"C:\Windows\SysWOW64\bit4xpki.dll",
            r"C:\Program Files\BIT4ID\eToken\pkcs11\bit4id_pkcs11.dll",
            r"C:\Program Files (x86)\BIT4ID\eToken\pkcs11\bit4id_pkcs11.dll",
        ],
        'gemalto': [
            r"C:\Program Files\Gemalto\IDGo 800 PKCS#11\IDPrimePKCS11.dll",
            r"C:\Program Files (x86)\Gemalto\IDGo 800 PKCS#11\IDPrimePKCS11.dll",
            r"C:\Program Files\Gemalto\Classic Client\BIN\gclib.dll",
            r"C:\Program Files (x86)\Gemalto\Classic Client\BIN\gclib.dll",
        ],
        'ica': [
            r"C:\Program Files\I.CA\PKCS11\ica_pkcs11.dll",
            r"C:\Program Files (x86)\I.CA\PKCS11\ica_pkcs11.dll",
            r"C:\Windows\System32\ica_pkcs11.dll",
            r"C:\Windows\SysWOW64\ica_pkcs11.dll",
        ],
        'generic': [
            r"C:\Windows\System32\pkcs11.dll",
            r"C:\Windows\SysWOW64\pkcs11.dll",
            "pkcs11.dll",  # Pokud je v PATH
        ]
    }
    
    # Pokud je zadán konkrétní typ, hledáme pouze ten
    if token_type and token_type.lower() in pkcs11_libraries:
        for path in pkcs11_libraries[token_type.lower()]:
            if os.path.isfile(path):
                logger.info(f"Nalezena PKCS#11 knihovna ({token_type}): {path}")
                return path
        return None
    
    # Automatická detekce - procházíme všechny typy
    for token_type_name, paths in pkcs11_libraries.items():
        for path in paths:
            if os.path.isfile(path):
                logger.info(f"Nalezena PKCS#11 knihovna ({token_type_name}): {path}")
                return path
    
    return None


def find_all_pkcs11_libraries() -> List[Tuple[str, str]]:
    """
    Najde všechny dostupné PKCS#11 knihovny v systému.
    
    Returns:
        Seznam tuple (cesta, typ_tokenu)
    """
    found = []
    token_types = ['safenet', 'bit4id', 'gemalto', 'ica', 'generic']
    
    for token_type in token_types:
        lib_path = find_pkcs11_library(token_type)
        if lib_path:
            found.append((lib_path, token_type))
    
    return found


def list_certificates_from_token(pkcs11_lib: str, pin: Optional[str] = None, slot_no: int = 0) -> List[Dict[str, str]]:
    """
    Zobrazí seznam certifikátů na tokenu.
    
    Args:
        pkcs11_lib: Cesta k PKCS#11 knihovně
        pin: PIN pro token (pokud None, bude vyžádán)
        slot_no: Číslo slotu (0 = první slot)
    
    Returns:
        Seznam certifikátů: [{"label": "...", "subject": "...", "issuer": "...", "serial": "..."}, ...]
    """
    if not PKCS11_AVAILABLE:
        return []
    
    try:
        # Použijeme pyhanko PKCS11SigningContext - to je nejspolehlivější způsob
        # pyhanko správně komunikuje s tokenem a načítá certifikáty
        if PKCS11SigningContext is not None:
            try:
                with PKCS11SigningContext(pkcs11_lib, slot_no=slot_no, user_pin=pin) as ctx:
                    certs = []
                    # list_certs() vrací iterátor (cert_label, cert_obj) tuple
                    for cert_label, cert_obj in ctx.list_certs():
                        try:
                            # Získáme informace z certifikátu
                            subject = cert_obj.subject.rfc4514_string() if hasattr(cert_obj.subject, 'rfc4514_string') else str(cert_obj.subject)
                            issuer = cert_obj.issuer.rfc4514_string() if hasattr(cert_obj.issuer, 'rfc4514_string') else str(cert_obj.issuer)
                            serial = hex(cert_obj.serial_number)[2:].upper() if hasattr(cert_obj, 'serial_number') else "N/A"
                            certs.append({
                                "label": cert_label,
                                "subject": subject,
                                "issuer": issuer,
                                "serial": serial
                            })
                        except Exception as e:
                            logger.warning(f"Chyba při načítání certifikátu {cert_label}: {e}")
                            import traceback
                            logger.debug(traceback.format_exc())
                    return certs
            except Exception as e:
                logger.warning(f"Chyba při načítání certifikátů pomocí pyhanko: {e}")
                # Fallback na python-pkcs11 (pokud je dostupné)
                if PKCS11_AVAILABLE:
                    try:
                        from pkcs11 import lib, ObjectClass, Attribute
                        
                        # Načteme PKCS#11 knihovnu
                        pkcs11_lib_obj = lib(pkcs11_lib)
                        
                        # Získáme tokeny (get_tokens() vrací generátor)
                        tokens = list(pkcs11_lib_obj.get_tokens())
                        if not tokens:
                            logger.warning("Nenalezeny žádné tokeny")
                            return []
                        
                        # Použijeme první token nebo zadaný slot
                        token = tokens[slot_no] if slot_no < len(tokens) else tokens[0]
                        
                        certs = []
                        with token.open(user_pin=pin) as session:
                            # Najdeme všechny certifikáty
                            for obj in session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}):
                                try:
                                    # Získáme certifikát jako bytes
                                    cert_data = bytes(obj[Attribute.VALUE])
                                    
                                    # Načteme certifikát pomocí cryptography
                                    from cryptography import x509
                                    from cryptography.hazmat.backends import default_backend
                                    
                                    cert = x509.load_der_x509_certificate(cert_data, default_backend())
                                    
                                    # Získáme informace
                                    subject = cert.subject.rfc4514_string() if hasattr(cert.subject, 'rfc4514_string') else str(cert.subject)
                                    issuer = cert.issuer.rfc4514_string() if hasattr(cert.issuer, 'rfc4514_string') else str(cert.issuer)
                                    serial = hex(cert.serial_number)[2:].upper()
                                    
                                    # Zkusíme najít label
                                    label = None
                                    try:
                                        label_attr = obj.get(Attribute.LABEL)
                                        if label_attr:
                                            if isinstance(label_attr, bytes):
                                                label = label_attr.decode('utf-8', errors='ignore')
                                            else:
                                                label = str(label_attr)
                                    except:
                                        pass
                                    
                                    if not label:
                                        # Vytvoříme label z CN
                                        try:
                                            cn = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
                                            label = cn
                                        except:
                                            label = f"Cert_{serial[:8]}"
                                    
                                    certs.append({
                                        "label": label,
                                        "subject": subject,
                                        "issuer": issuer,
                                        "serial": serial
                                    })
                                except Exception as e:
                                    logger.warning(f"Chyba při načítání certifikátu: {e}")
                                    continue
                        
                        return certs
                    except Exception as e2:
                        logger.error(f"Chyba při načítání certifikátů pomocí python-pkcs11: {e2}")
                        return []
                else:
                    return []
        else:
            logger.warning("pyhanko.keys.pkcs11 není dostupné - nelze načíst certifikáty z tokenu")
            return []
                
    except Exception as e:
        logger.error(f"Chyba při načítání certifikátů z tokenu: {e}")
        return []


def sign_pdf(
    input_path: str,
    output_path: Optional[str] = None,
    options: Optional[SigningOptions] = None
) -> Tuple[bool, str]:
    """
    Podepíše PDF soubor pomocí certifikátu z tokenu nebo .pfx souboru.
    
    Args:
        input_path: Cesta ke vstupnímu PDF
        output_path: Cesta k výstupnímu PDF (pokud None, přidá _signed suffix)
        options: Nastavení podepisování
    
    Returns:
        Tuple (success, message)
    """
    # pyHanko je POVINNÉ - kontrola byla provedena při importu
    if not PYHANKO_AVAILABLE:
        raise ImportError("pyhanko není nainstalován. Instalujte: pip install pyhanko pyhanko-certvalidator")
    
    input_path = Path(input_path)
    if not input_path.exists():
        return False, f"Soubor neexistuje: {input_path}"
    
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_signed{input_path.suffix}"
    else:
        output_path = Path(output_path)
    
    if options is None:
        options = SigningOptions()
    
    # Pokud je page_number -1 nebo signature_position je auto, použijeme poslední stránku a pravý dolní roh
    if options.page_number < 0 or options.signature_position == (-1, -1, -1, -1):
        # Zjistíme počet stránek a velikost stránky pomocí pikepdf (POVINNÉ)
        try:
            import pikepdf
        except ImportError:
            error_msg = (
                "Kritická chyba: pikepdf není nainstalován.\n\n"
                "Spusťte: pip install pikepdf"
            )
            logger.error(error_msg)
            # Zkusíme zobrazit popup pokud je k dispozici tkinter
            try:
                import tkinter.messagebox as mb
                mb.showerror("Kritická chyba", error_msg)
            except:
                pass
            raise ImportError(error_msg)
        
        try:
            with pikepdf.open(str(input_path)) as pdf:
                num_pages = len(pdf.pages)
                if num_pages > 0:
                    # Použijeme poslední stránku (index je 0-based)
                    options.page_number = num_pages - 1
                    
                    # Získáme velikost stránky
                    page = pdf.pages[options.page_number]
                    media_box = page.MediaBox
                    page_width = float(media_box[2] - media_box[0])  # width = x1 - x0
                    page_height = float(media_box[3] - media_box[1])  # height = y1 - y0
                    
                    # Vypočítáme pozici v pravém dolním rohu podle specifikace
                    # Position = Right-Bottom (x: width-170, y: 20, width: 150, height: 60)
                    sig_width = 150  # Šířka podpisu
                    sig_height = 60   # Výška podpisu
                    x_offset = 170    # Offset od pravého okraje
                    y_offset = 20    # Offset od dolního okraje
                    
                    x0 = page_width - x_offset
                    y0 = y_offset
                    x1 = x0 + sig_width
                    y1 = y0 + sig_height
                    
                    options.signature_position = (x0, y0, x1, y1)
                    logger.info(f"Automatické umístění podpisu: stránka {options.page_number + 1}, pozice ({x0:.1f}, {y0:.1f}, {x1:.1f}, {y1:.1f})")
        except ImportError:
            error_msg = (
                "pikepdf není nainstalován! Podepisování vyžaduje pikepdf pro čtení PDF metadat.\n\n"
                "Spusťte: pip install pikepdf"
            )
            logger.error(error_msg)
            # Zkusíme zobrazit popup pokud je k dispozici tkinter
            try:
                import tkinter.messagebox as mb
                mb.showerror("Kritická chyba", error_msg)
            except:
                pass
            raise ImportError(error_msg)
        except Exception as e:
            logger.warning(f"Nepodařilo se zjistit počet stránek, použije se výchozí nastavení: {e}")
            # Použijeme výchozí hodnoty
            if options.page_number < 0:
                options.page_number = 0
            if options.signature_position == (-1, -1, -1, -1):
                # Výchozí pozice: width-170, y: 20, width: 150, height: 60 (předpokládáme A4 = 595x842)
                options.signature_position = (425, 20, 575, 80)
    
    try:
        # Vytvoříme signer
        if options.pkcs11_lib:
            # Podepisování pomocí hardware tokenu (PKCS#11)
            return _sign_with_pkcs11(input_path, output_path, options)
        elif options.certificate_path:
            # Podepisování pomocí .pfx/.p12 souboru
            return _sign_with_pfx(input_path, output_path, options)
        else:
            return False, "Není zadán certifikát (token nebo .pfx soubor)"
    
    except SigningError as e:
        logger.exception(f"Chyba při podepisování (SigningError): {e}")
        error_str = str(e).lower()
        if "password" in error_str or "heslo" in error_str:
            return False, "Nesprávné heslo pro certifikát. Zkontrolujte zadané heslo."
        elif "tsa" in error_str or "timestamp" in error_str:
            return False, "Chyba při komunikaci s TSA serverem (PostSignum). Zkontrolujte připojení k internetu."
        else:
            return False, f"Chyba při podepisování: {str(e)}"
    except Exception as e:
        logger.exception(f"Chyba při podepisování: {e}")
        error_str = str(e).lower()
        if "password" in error_str or "heslo" in error_str:
            return False, "Nesprávné heslo pro certifikát. Zkontrolujte zadané heslo."
        elif "tsa" in error_str or "timestamp" in error_str:
            return False, "Chyba při komunikaci s TSA serverem (PostSignum). Zkontrolujte připojení k internetu."
        else:
            return False, f"Chyba při podepisování: {str(e)}"


def _sign_with_pkcs11(
    input_path: Path,
    output_path: Path,
    options: SigningOptions
) -> Tuple[bool, str]:
    """Podepisování pomocí PKCS#11 (hardware token) - podporuje BIT4ID, SafeNet, Gemalto, I.CA"""
    if not PKCS11_AVAILABLE:
        return False, "PKCS#11 podpora není dostupná. Instalujte: pip install python-pkcs11"
    
    try:
        # Použijeme pyhanko PKCS11SigningContext - to je správný způsob
        # pyhanko správně komunikuje s tokenem a načítá certifikát i klíč
        if PKCS11SigningContext is not None:
            try:
                # Nejprve zkusíme načíst certifikáty, abychom ověřili, že token funguje
                certs = list_certificates_from_token(options.pkcs11_lib, options.token_pin, slot_no=0)
                if not certs:
                    return False, "Na tokenu nebyly nalezeny žádné certifikáty. Zkontrolujte PIN a připojení tokenu."
                
                # Pokud je zadán label, ověříme, že existuje
                if options.certificate_label:
                    found = any(cert.get('label') == options.certificate_label for cert in certs)
                    if not found:
                        return False, f"Certifikát s labelem '{options.certificate_label}' nebyl nalezen na tokenu."
                
                # Použijeme pyhanko PKCS11SigningContext pro podepisování
                # Toto správně načte certifikát a privátní klíč z tokenu
                logger.info(f"Načítám certifikát z tokenu (label: {options.certificate_label or 'první dostupný'})...")
                with PKCS11SigningContext(
                    options.pkcs11_lib,
                    slot_no=0,
                    user_pin=options.token_pin,
                    cert_label=options.certificate_label
                ) as signing_context:
                    # Ověříme, že máme certifikát a klíč
                    if not hasattr(signing_context, 'cert') or not signing_context.cert:
                        return False, "Nepodařilo se načíst certifikát z tokenu."
                    
                    logger.info(f"Certifikát načten: {signing_context.cert.subject}")
                    return _sign_with_pyhanko_context(input_path, output_path, options, signing_context)
            except Exception as e:
                logger.exception(f"Chyba při podepisování s PKCS11SigningContext: {e}")
                return False, f"Chyba při podepisování: {str(e)}"
        else:
            return False, "pyhanko.keys.pkcs11 není dostupné. Instalujte: pip install 'pyhanko[pkcs11]'"
                
    except Exception as e:
        logger.exception(f"Chyba při podepisování s PKCS#11: {e}")
        return False, f"Chyba PKCS#11: {str(e)}"


def _sign_with_pyhanko_context(
    input_path: Path,
    output_path: Path,
    options: SigningOptions,
    signing_context
) -> Tuple[bool, str]:
    """Pomocná funkce pro podepisování s pyhanko kontextem"""
    try:
        # Získáme jméno z certifikátu
        try:
            cert_subject = signing_context.cert.subject
            signer_name = cert_subject.rfc4514_string() if hasattr(cert_subject, 'rfc4514_string') else str(cert_subject)
        except:
            signer_name = "Elektronický podpis"
        
        # Vytvoříme metadata podpisu nebo razítka
        from pyhanko.sign.signers.pdf_signer import PdfSignatureMetadata
        
        # Upravíme reason podle typu
        if options.signature_type == "razitko":
            reason_text = options.reason if options.reason else "Elektronické autorizační razítko"
        else:
            reason_text = options.reason if options.reason else "Elektronický podpis"
        
        metadata = PdfSignatureMetadata(
            field_name=options.signature_field_name,
            reason=reason_text,
            location=options.location,
            contact_info=options.contact_info,
            name=signer_name  # Použijeme 'name' místo 'signer_name' podle pyHanko API
        )
        
        # TSA (časové razítko) - PostSignum TSA pomocí HTTPTimeStamper
        timestamper = None
        HTTPTimeStamper_class = None
        if options.use_tsa and options.tsa_url:
            try:
                from pyhanko.sign.timestamps import HTTPTimeStamper
                from requests.auth import HTTPBasicAuth
                HTTPTimeStamper_class = HTTPTimeStamper
                # PostSignum TSA s timeoutem 5 sekund
                tsa_url = options.tsa_url
                
                # HTTP Basic Authentication (pokud jsou zadány přihlašovací údaje)
                auth = None
                if options.tsa_username and options.tsa_password:
                    auth = HTTPBasicAuth(options.tsa_username, options.tsa_password)
                    logger.info(f"TSA inicializováno s autentizací: {tsa_url} (timeout: 5s)")
                else:
                    logger.info(f"TSA inicializováno: {tsa_url} (timeout: 5s, bez autentizace)")
                
                timestamper = HTTPTimeStamper(url=tsa_url, timeout=5, auth=auth)
            except ImportError as e:
                logger.warning(f"HTTPTimeStamper nebo requests není dostupný: {e}, TSA nebude použito")
                timestamper = None
            except Exception as e:
                logger.warning(f"Chyba při vytváření HTTPTimeStamper: {e}, TSA nebude použito")
                timestamper = None
        elif options.use_tsa and not options.tsa_url:
            logger.warning("TSA je povoleno, ale není zadána URL. TSA nebude použito.")
        
        # Vytvoříme signer
        # POZOR: PdfSigner má signaturu: PdfSigner(signature_meta, signer, *, timestamper=...)
        # Takže signature_meta je první pozicní argument, signer je druhý
        
        # PdfSigner podporuje pouze timestamper objekt, ne timestamp_url
        signer = signers.PdfSigner(
            metadata,
            signing_context,
            timestamper=timestamper if timestamper else None
        )
        
        # Vytvoříme PdfFileWriter a načteme vstupní PDF
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.pdf_utils.writer import copy_into_new_writer
        
        with open(input_path, 'rb') as inf:
            reader = PdfFileReader(inf)
            # Zkopírujeme celý PDF do nového writeru (správný způsob - řeší problém s RawContent)
            writer = copy_into_new_writer(reader)
            
            # Vizuální podpis (čárové razítko) - připravíme field spec a appearance
            new_field_spec = None
            appearance_text_params = None
            if options.visual_signature:
                try:
                    appearance_text = _create_signature_appearance_text(signing_context.cert, options)
                    # Vytvoříme SigFieldSpec pro nové pole
                    new_field_spec = SigFieldSpec(
                        options.signature_field_name,
                        box=options.signature_position,
                        on_page=options.page_number
                    )
                    
                    # Nastavíme appearance text params
                    appearance_text_params = {'text': appearance_text}
                except Exception as e:
                    logger.warning(f"Chyba při přidávání vizuálního podpisu: {e}")
                    new_field_spec = None
                    appearance_text_params = None
        
        # Vytvoříme PdfSigner s new_field_spec v konstruktoru (pokud ještě není vytvořen)
        if 'signer' not in locals() or signer is None:
            signer = signers.PdfSigner(
                metadata,
                signing_context,
                timestamper=timestamper if timestamper else None,
                new_field_spec=new_field_spec
            )
        else:
            # Pokud už existuje, musíme vytvořit nový s new_field_spec
            signer = signers.PdfSigner(
                metadata,
                signing_context,
                timestamper=timestamper if timestamper else None,
                new_field_spec=new_field_spec
            )
        
        # Podepíšeme PDF
        with open(output_path, 'wb') as outf:
            signer.sign_pdf(
                pdf_out=writer,
                appearance_text_params=appearance_text_params,
                output=outf
            )
        
        return True, f"PDF podepsáno pomocí tokenu → {output_path.name}"
    
    except Exception as e:
        logger.exception(f"Chyba při podepisování s PKCS#11: {e}")
        return False, f"Chyba PKCS#11: {str(e)}"


def _sign_with_pfx(
    input_path: Path,
    output_path: Path,
    options: SigningOptions
) -> Tuple[bool, str]:
    """Podepisování pomocí .pfx/.p12 souboru pomocí pyHanko P12Signer"""
    try:
        from pyhanko.sign.signers.pdf_cms import signer_from_p12_config, PKCS12SignatureConfig
        
        # Načteme .pfx soubor
        cert_path = Path(options.certificate_path)
        if not cert_path.exists():
            return False, f"Certifikát neexistuje: {cert_path}"
        
        # Heslo pro .pfx soubor (potřebujeme i pro načtení certifikátu pro metadata)
        pfx_password = options.token_pin if options.token_pin else None
        pfx_passphrase_bytes = None
        if pfx_password:
            pfx_passphrase_bytes = pfx_password.encode() if isinstance(pfx_password, str) else pfx_password
        
        # Pokud máme předověřený signer objekt, použijeme ho (pro batch processing)
        if options.verified_signer is not None:
            signer_obj = options.verified_signer
            logger.info("Používám předověřený signer objekt")
        else:
            
            # Použijeme pyhanko's PKCS12SignatureConfig a signer_from_p12_config
            try:
                p12_config = PKCS12SignatureConfig(
                    pfx_file=str(cert_path),
                    pfx_passphrase=pfx_passphrase_bytes
                )
                signer_obj = signer_from_p12_config(p12_config)
            except Exception as e:
                # Zkusíme bez hesla
                try:
                    p12_config = PKCS12SignatureConfig(
                        pfx_file=str(cert_path),
                        pfx_passphrase=None
                    )
                    signer_obj = signer_from_p12_config(p12_config)
                except:
                    # Zkusíme prázdné heslo
                    try:
                        p12_config = PKCS12SignatureConfig(
                            pfx_file=str(cert_path),
                            pfx_passphrase=b""
                        )
                        signer_obj = signer_from_p12_config(p12_config)
                    except Exception as e2:
                        return False, f"Nepodařilo se načíst certifikát z .pfx souboru. Zkontrolujte heslo. Chyba: {str(e2)}"
        
        # Získáme certifikát pro metadata
        # Pokud máme informace o certifikátu z validace, použijeme je
        if options.certificate_info and 'expiration_date' in options.certificate_info:
            # Použijeme informace z předověřeného certifikátu
            certificate = None  # Nemusíme načítat znovu
            signer_name = options.certificate_info.get('common_name', 'Elektronický podpis')
        else:
            # Načteme certifikát pro metadata
            try:
                from cryptography.hazmat.primitives.serialization import pkcs12
                from cryptography.hazmat.backends import default_backend
                with open(cert_path, 'rb') as f:
                    pfx_data = f.read()
                # Zkusíme s různými hesly
                certificate = None
                for test_pwd in [pfx_passphrase_bytes, None, b""]:
                    try:
                        _, certificate, _ = pkcs12.load_key_and_certificates(
                            pfx_data,
                            test_pwd,
                            backend=default_backend()
                        )
                        if certificate:
                            break
                    except:
                        continue
            except:
                certificate = None
            
            # Získáme jméno z certifikátu
            try:
                if certificate:
                    cert_subject = certificate.subject
                    signer_name = cert_subject.rfc4514_string() if hasattr(cert_subject, 'rfc4514_string') else str(cert_subject)
                else:
                    signer_name = "Elektronický podpis"
            except:
                signer_name = "Elektronický podpis"
        
        # Vytvoříme metadata podpisu nebo razítka
        from pyhanko.sign.signers.pdf_signer import PdfSignatureMetadata
        
        # Upravíme reason podle typu
        if options.signature_type == "razitko":
            reason_text = options.reason if options.reason else "Elektronické autorizační razítko"
        else:
            reason_text = options.reason if options.reason else "Elektronický podpis"
        
        metadata = PdfSignatureMetadata(
            field_name=options.signature_field_name,
            reason=reason_text,
            location=options.location,
            contact_info=options.contact_info,
            name=signer_name  # Použijeme 'name' místo 'signer_name' podle pyHanko API
        )
        
        # TSA (časové razítko) - PostSignum TSA pomocí HTTPTimeStamper
        timestamper = None
        HTTPTimeStamper_class = None
        if options.use_tsa and options.tsa_url:
            try:
                from pyhanko.sign.timestamps import HTTPTimeStamper
                from requests.auth import HTTPBasicAuth
                HTTPTimeStamper_class = HTTPTimeStamper
                # PostSignum TSA s timeoutem 5 sekund
                tsa_url = options.tsa_url
                
                # HTTP Basic Authentication (pokud jsou zadány přihlašovací údaje)
                auth = None
                if options.tsa_username and options.tsa_password:
                    auth = HTTPBasicAuth(options.tsa_username, options.tsa_password)
                    logger.info(f"TSA inicializováno s autentizací: {tsa_url} (timeout: 5s)")
                else:
                    logger.info(f"TSA inicializováno: {tsa_url} (timeout: 5s, bez autentizace)")
                
                timestamper = HTTPTimeStamper(url=tsa_url, timeout=5, auth=auth)
            except ImportError as e:
                logger.warning(f"HTTPTimeStamper nebo requests není dostupný: {e}, TSA nebude použito")
                timestamper = None
            except Exception as e:
                logger.warning(f"Chyba při vytváření HTTPTimeStamper: {e}, TSA nebude použito")
                timestamper = None
        elif options.use_tsa and not options.tsa_url:
            logger.warning("TSA je povoleno, ale není zadána URL. TSA nebude použito.")
        
        # Memory-First Approach: Použijeme BytesIO jako mezibuffer pro bezpečné načtení PDF
        # Toto řeší problém s "Illegal PDF header" když pikepdf a pyHanko pracují se stejným souborem
        
        # Krok 1: Načteme PDF do paměťového bufferu
        temp_buffer = io.BytesIO()
        with open(input_path, 'rb') as inf:
            pdf_data = inf.read()
            temp_buffer.write(pdf_data)
            temp_buffer.seek(0)  # CRUCIAL: Resetujeme pozici na začátek
        
        # Krok 2: Vytvoříme PdfFileWriter z bufferu pomocí pyHanko
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.pdf_utils.writer import copy_into_new_writer
        
        # Načteme PDF z bufferu
        reader = PdfFileReader(temp_buffer)
        # Zkopírujeme celý PDF do nového writeru (správný způsob - řeší problém s RawContent)
        writer = copy_into_new_writer(reader)
        
        # Uzavřeme buffer (už ho nepotřebujeme)
        temp_buffer.close()
        
        # Vizuální podpis (čárové razítko) - připravíme field spec a appearance
        new_field_spec = None
        appearance_text_params = None
        if options.visual_signature:
            # Pokud máme certificate_info, použijeme ho pro vytvoření appearance
            if options.certificate_info and 'expiration_date' in options.certificate_info:
                # Použijeme skutečný certifikát pokud je k dispozici, jinak info z certificate_info
                if certificate:
                    appearance_text = _create_signature_appearance_text(certificate, options)
                else:
                    # Vytvoříme jednoduchý text z certificate_info
                    cn = options.certificate_info.get('common_name', 'Neznámé')
                    appearance_text = f"Elektronický podpis\n{cn}"
            elif certificate:
                appearance_text = _create_signature_appearance_text(certificate, options)
            else:
                appearance_text = "Elektronický podpis"
            
            # Vytvoříme SigFieldSpec pro nové pole
            new_field_spec = SigFieldSpec(
                options.signature_field_name,
                box=options.signature_position,
                on_page=options.page_number
            )
            
            # Nastavíme appearance text params
            appearance_text_params = {'text': appearance_text}
        else:
            new_field_spec = None
            appearance_text_params = None
        
        # Vytvoříme PdfSigner s new_field_spec v konstruktoru
        # POZOR: PdfSigner má signaturu: PdfSigner(signature_meta, signer, *, timestamper=..., new_field_spec=...)
        # PdfSigner podporuje pouze timestamper objekt, ne timestamp_url
        signer = signers.PdfSigner(
            metadata,
            signer_obj,
            timestamper=timestamper if timestamper else None,
            new_field_spec=new_field_spec
        )
        
        # Krok 3: Podepíšeme PDF a uložíme do finálního souboru
        with open(output_path, 'wb') as outf:
            signer.sign_pdf(
                pdf_out=writer,
                appearance_text_params=appearance_text_params,
                output=outf
            )
        
        return True, f"PDF podepsáno pomocí .pfx certifikátu → {output_path.name}"
    
    except SigningError as e:
        logger.exception(f"Chyba při podepisování s .pfx (SigningError): {e}")
        return False, f"Chyba při podepisování: {str(e)}"
    except Exception as e:
        logger.exception(f"Chyba při podepisování s .pfx: {e}")
        # Zkontrolujeme zda je to chyba pyhanko
        error_str = str(e).lower()
        if "password" in error_str or "heslo" in error_str:
            return False, "Nesprávné heslo pro .pfx soubor. Zkontrolujte zadané heslo."
        elif "tsa" in error_str or "timestamp" in error_str:
            return False, "Chyba při komunikaci s TSA serverem. Zkontrolujte připojení k internetu."
        else:
            return False, f"Chyba při podepisování: {str(e)}"


def _create_signature_appearance_text(certificate, options: SigningOptions) -> str:
    """
    Vytvoří text pro vizuální podpis nebo autorizační razítko (čárové razítko).
    
    Args:
        certificate: Certifikát
        options: Nastavení podepisování
    
    Returns:
        Text pro zobrazení podpisu/razítka
    """
    # Získáme jméno z certifikátu
    try:
        subject = certificate.subject
        # Zkusíme najít CN (Common Name)
        cn = None
        for attr in subject:
            if hasattr(attr, 'oid') and hasattr(attr.oid, '_name') and attr.oid._name == 'commonName':
                cn = attr.value
                break
            elif hasattr(attr, 'rfc4514_string'):
                # Zkusíme parsovat z rfc4514_string
                cn_str = attr.rfc4514_string()
                if 'CN=' in cn_str:
                    cn = cn_str.split('CN=')[1].split(',')[0].strip()
                    break
        
        name = cn or str(subject)
    except:
        name = "Elektronický podpis"
    
    # Rozlišení mezi podpisem a autorizačním razítkem
    if options.signature_type == "razitko":
        # Autorizační razítko
        title = "ELEKTRONICKÉ AUTORIZAČNÍ RAZÍTKO"
        icon = "🔐"
    else:
        # Obyčejný podpis
        title = "ELEKTRONICKÝ PODPIS"
        icon = "✍"
    
    # Vytvoříme text pro čárové razítko (podobně jako PDF XChange, Adobe Acrobat, iSignum)
    appearance_lines = [
        "═══════════════════════════════════",
        f"  {icon} {title}",
        "═══════════════════════════════════",
        f"  {name}",
        "",
        f"  Lokace: {options.location}",
        f"  Důvod: {options.reason}",
    ]
    
    if options.use_tsa:
        appearance_lines.append("  ⏰ S časovým razítkem (TSA)")
    
    appearance_lines.append("═══════════════════════════════════")
    
    return "\n".join(appearance_lines)


def sign_pdf_batch(
    input_files: List[str],
    options: SigningOptions,
    output_dir: Optional[str] = None
) -> List[Tuple[str, bool, str]]:
    """
    Dávkové podepisování více PDF souborů.
    
    Args:
        input_files: Seznam cest k PDF souborům
        options: Nastavení podepisování
        output_dir: Výstupní složka (pokud None, použije se stejná složka)
    
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
            output_path = output_dir / f"{input_path.stem}_signed{input_path.suffix}"
        else:
            output_path = None
        
        success, message = sign_pdf(str(input_path), str(output_path) if output_path else None, options)
        results.append((input_path.name, success, message))
    
    return results


# Test
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Použití: python signer.py <input.pdf> [output.pdf]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Zkusíme najít PKCS#11 knihovnu
    pkcs11_lib = find_pkcs11_library()
    if pkcs11_lib:
        print(f"Nalezena PKCS#11 knihovna: {pkcs11_lib}")
        options = SigningOptions(pkcs11_lib=pkcs11_lib)
    else:
        print("PKCS#11 knihovna nenalezena. Použijte .pfx soubor.")
        options = SigningOptions()
    
    success, message = sign_pdf(input_file, output_file, options)
    print(f"{'✓' if success else '✗'} {message}")
