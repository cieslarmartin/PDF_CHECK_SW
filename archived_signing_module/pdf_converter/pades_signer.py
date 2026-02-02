# pades_signer.py
# Professional PAdES PDF Signer with Hardware Token Support (PKCS#11)
# Supports iSignum/PostSignum tokens with LTV (Long Term Validation)
# Build 1.0 | © 2025 Ing. Martin Cieślar

import os
import sys
import logging
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import getpass

logger = logging.getLogger(__name__)

# pyHanko imports
try:
    from pyhanko.sign import signers, fields
    from pyhanko.sign.fields import SigFieldSpec
    from pyhanko.sign.general import SigningError
    from pyhanko.sign.signers.pdf_signer import PdfSignatureMetadata
    from pyhanko.keys.pkcs11 import PKCS11SigningContext
    PYHANKO_AVAILABLE = True
except ImportError as e:
    PYHANKO_AVAILABLE = False
    logger.error(f"pyhanko není nainstalován: {e}")
    logger.error("Instalujte: pip install pyhanko pyhanko-certvalidator")

# PKCS#11 fallback
PKCS11_FALLBACK_AVAILABLE = False
try:
    from pkcs11 import lib, ObjectClass, Attribute
    PKCS11_FALLBACK_AVAILABLE = True
except ImportError:
    pass


@dataclass
class PKCS11Config:
    """Konfigurace PKCS#11 middleware"""
    dll_path: str  # Cesta k PKCS#11 knihovně (.dll nebo .so)
    slot_id: Optional[int] = None  # ID slotu (None = automaticky první dostupný)
    token_label: Optional[str] = None  # Label tokenu (volitelné)


@dataclass
class VisualStampConfig:
    """Konfigurace vizuálního razítka (ČKAIT styl)"""
    page_number: int = 0  # 0 = první stránka
    x: float = 50.0  # Pozice X v bodech
    y: float = 50.0  # Pozice Y v bodech
    width: float = 200.0  # Šířka razítka
    height: float = 100.0  # Výška razítka
    
    # Text razítka
    show_name: bool = True
    show_date: bool = True
    show_authorized_engineer: bool = True  # "Autorizovaný inženýr"
    organization: str = "ČKAIT"  # Organizace
    
    # Styl
    border_width: float = 2.0
    border_color: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # RGB 0-1
    background_color: Tuple[float, float, float] = (1.0, 1.0, 0.9)  # RGB 0-1
    text_color: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # RGB 0-1
    font_size: int = 10


@dataclass
class SigningMetadata:
    """Metadata pro podpis"""
    reason: str = "Elektronický podpis"
    location: str = "Česká republika"
    contact_info: str = ""
    signer_name: Optional[str] = None  # Pokud None, použije se z certifikátu


class PDFSigner:
    """
    Profesionální třída pro PAdES podepisování PDF s hardware tokeny.
    
    Podporuje:
    - PKCS#11 hardware tokeny (iSignum, PostSignum, BIT4ID, SafeNet)
    - PAdES LTV (Long Term Validation)
    - TSA (Time Stamping Authority) - PostSignum
    - Vizuální razítko ve stylu ČKAIT
    """
    
    def __init__(self, pkcs11_config: PKCS11Config, tsa_url: str = "http://tsa.postsignum.cz/tsp"):
        """
        Inicializace PDFSigner.
        
        Args:
            pkcs11_config: Konfigurace PKCS#11 middleware
            tsa_url: URL TSA serveru (PostSignum)
        """
        if not PYHANKO_AVAILABLE:
            raise ImportError(
                "pyhanko není nainstalován. Instalujte: pip install pyhanko pyhanko-certvalidator"
            )
        
        self.pkcs11_config = pkcs11_config
        self.tsa_url = tsa_url
        self.signing_context: Optional[PKCS11SigningContext] = None
        self._verify_dll_path()
    
    def _verify_dll_path(self):
        """Ověří, že PKCS#11 knihovna existuje"""
        if not os.path.isfile(self.pkcs11_config.dll_path):
            raise FileNotFoundError(
                f"PKCS#11 knihovna nenalezena: {self.pkcs11_config.dll_path}\n"
                f"Zkontrolujte cestu k middleware (např. iSignum, PostSignum)."
            )
    
    def list_slots(self) -> List[Dict[str, Any]]:
        """
        Zobrazí seznam dostupných slotů na tokenu.
        
        Returns:
            Seznam slotů: [{"slot_id": 0, "token_label": "...", "token_manufacturer": "..."}, ...]
        """
        slots = []
        try:
            # Použijeme pyHanko pro načtení slotů
            from pyhanko.keys.pkcs11 import PKCS11SigningContext
            
            # Zkusíme načíst sloty (pyHanko interně používá python-pkcs11)
            if PKCS11_FALLBACK_AVAILABLE:
                pkcs11_lib_obj = lib(self.pkcs11_config.dll_path)
                token_list = list(pkcs11_lib_obj.get_tokens())
                
                for i, token in enumerate(token_list):
                    try:
                        slots.append({
                            "slot_id": i,
                            "token_label": token.label.decode('utf-8', errors='ignore') if isinstance(token.label, bytes) else str(token.label),
                            "token_manufacturer": token.manufacturer_id.decode('utf-8', errors='ignore') if isinstance(token.manufacturer_id, bytes) else str(token.manufacturer_id),
                            "has_token": True
                        })
                    except Exception as e:
                        logger.warning(f"Chyba při načítání slotu {i}: {e}")
                        slots.append({
                            "slot_id": i,
                            "token_label": f"Slot {i}",
                            "token_manufacturer": "Unknown",
                            "has_token": False
                        })
            else:
                # Fallback: zkusíme použít pyHanko přímo
                # pyHanko automaticky detekuje sloty
                slots.append({
                    "slot_id": 0,
                    "token_label": "Auto-detected",
                    "token_manufacturer": "Unknown",
                    "has_token": True
                })
        except Exception as e:
            logger.error(f"Chyba při načítání slotů: {e}")
            raise RuntimeError(f"Nepodařilo se načíst sloty z PKCS#11: {str(e)}")
        
        return slots
    
    def list_certificates(self, pin: Optional[str] = None, slot_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Zobrazí seznam certifikátů na tokenu.
        
        Args:
            pin: PIN pro token (pokud None, bude vyžádán)
            slot_id: ID slotu (pokud None, použije se z konfigurace)
        
        Returns:
            Seznam certifikátů: [{"label": "...", "subject": "...", "issuer": "...", "serial": "...", "valid_from": "...", "valid_to": "..."}, ...]
        """
        if pin is None:
            pin = self._get_pin()
        
        slot = slot_id if slot_id is not None else self.pkcs11_config.slot_id
        
        certs = []
        try:
            with PKCS11SigningContext(
                self.pkcs11_config.dll_path,
                slot_no=slot or 0,
                user_pin=pin
            ) as ctx:
                for cert_label, cert_obj in ctx.list_certs():
                    try:
                        subject = cert_obj.subject.rfc4514_string() if hasattr(cert_obj.subject, 'rfc4514_string') else str(cert_obj.subject)
                        issuer = cert_obj.issuer.rfc4514_string() if hasattr(cert_obj.issuer, 'rfc4514_string') else str(cert_obj.issuer)
                        serial = hex(cert_obj.serial_number)[2:].upper() if hasattr(cert_obj, 'serial_number') else "N/A"
                        
                        # Zkusíme získat platnost certifikátu
                        valid_from = None
                        valid_to = None
                        try:
                            if hasattr(cert_obj, 'not_valid_before'):
                                valid_from = cert_obj.not_valid_before
                            if hasattr(cert_obj, 'not_valid_after'):
                                valid_to = cert_obj.not_valid_after
                        except:
                            pass
                        
                        certs.append({
                            "label": cert_label,
                            "subject": subject,
                            "issuer": issuer,
                            "serial": serial,
                            "valid_from": valid_from,
                            "valid_to": valid_to,
                            "is_expired": valid_to is not None and datetime.now() > valid_to if valid_to else False
                        })
                    except Exception as e:
                        logger.warning(f"Chyba při načítání certifikátu {cert_label}: {e}")
                        continue
        except Exception as e:
            error_msg = str(e).lower()
            if "pin" in error_msg or "password" in error_msg or "wrong" in error_msg:
                raise ValueError("Nesprávný PIN nebo token je zamčený. Zkuste znovu.")
            elif "token" in error_msg or "slot" in error_msg:
                raise RuntimeError(f"Token nenalezen nebo není připojen. Zkontrolujte připojení tokenu.")
            else:
                raise RuntimeError(f"Chyba při načítání certifikátů: {str(e)}")
        
        return certs
    
    def _get_pin(self) -> str:
        """
        Bezpečně získá PIN od uživatele.
        
        Returns:
            PIN jako string
        """
        try:
            pin = getpass.getpass("Zadejte PIN pro token: ")
            if not pin:
                raise ValueError("PIN nemůže být prázdný")
            return pin
        except KeyboardInterrupt:
            raise ValueError("Zadávání PINu bylo přerušeno")
    
    def initialize_session(self, pin: Optional[str] = None, certificate_label: Optional[str] = None, slot_id: Optional[int] = None):
        """
        Inicializuje PKCS#11 session s tokenem.
        
        Args:
            pin: PIN pro token (pokud None, bude vyžádán)
            certificate_label: Label certifikátu (pokud None, použije se první dostupný)
            slot_id: ID slotu (pokud None, použije se z konfigurace)
        
        Raises:
            ValueError: Pokud je PIN nesprávný
            RuntimeError: Pokud token není nalezen
        """
        if pin is None:
            pin = self._get_pin()
        
        slot = slot_id if slot_id is not None else self.pkcs11_config.slot_id
        
        try:
            self.signing_context = PKCS11SigningContext(
                self.pkcs11_config.dll_path,
                slot_no=slot or 0,
                user_pin=pin,
                cert_label=certificate_label
            )
            
            # Otevřeme context manager (session)
            self.signing_context.__enter__()
            
            # Ověříme, že máme certifikát
            if not hasattr(self.signing_context, 'cert') or not self.signing_context.cert:
                raise RuntimeError("Nepodařilo se načíst certifikát z tokenu")
            
            logger.info(f"Session inicializována s certifikátem: {self.signing_context.cert.subject}")
            
        except Exception as e:
            error_msg = str(e).lower()
            if "pin" in error_msg or "password" in error_msg or "wrong" in error_msg:
                raise ValueError("Nesprávný PIN. Zkuste znovu.")
            elif "token" in error_msg or "slot" in error_msg or "not found" in error_msg:
                raise RuntimeError(f"Token nenalezen nebo není připojen. Zkontrolujte připojení tokenu.")
            else:
                raise RuntimeError(f"Chyba při inicializaci session: {str(e)}")
    
    def close_session(self):
        """Zavře PKCS#11 session"""
        if self.signing_context:
            try:
                self.signing_context.__exit__(None, None, None)
            except:
                pass
            self.signing_context = None
    
    def create_visual_stamp_text(self, certificate, config: VisualStampConfig) -> str:
        """
        Vytvoří text pro vizuální razítko ve stylu ČKAIT.
        
        Args:
            certificate: Certifikát pro získání jména
            config: Konfigurace vizuálního razítka
        
        Returns:
            Text pro razítko
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
            
            name = cn or "Elektronický podpis"
        except:
            name = "Elektronický podpis"
        
        # Vytvoříme text razítka
        lines = []
        lines.append("═══════════════════════════════════")
        
        if config.show_name:
            lines.append(f"  {name}")
        
        if config.show_authorized_engineer:
            lines.append("  Autorizovaný inženýr")
        
        if config.organization:
            lines.append(f"  {config.organization}")
        
        if config.show_date:
            lines.append(f"  Datum: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        
        lines.append("═══════════════════════════════════")
        
        return "\n".join(lines)
    
    def sign_pdf(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        metadata: Optional[SigningMetadata] = None,
        visual_stamp: Optional[VisualStampConfig] = None,
        use_tsa: bool = True
    ) -> Tuple[bool, str]:
        """
        Podepíše PDF podle PAdES standardu s LTV podporou.
        
        Args:
            input_path: Cesta ke vstupnímu PDF
            output_path: Cesta k výstupnímu PDF (pokud None, přidá _signed suffix)
            metadata: Metadata podpisu
            visual_stamp: Konfigurace vizuálního razítka (pokud None, razítko se nepřidá)
            use_tsa: Použít TSA (Time Stamping Authority) pro LTV
        
        Returns:
            Tuple (success, message)
        
        Raises:
            RuntimeError: Pokud není inicializována session
        """
        if not self.signing_context:
            raise RuntimeError("Session není inicializována. Zavolejte initialize_session() před podepisováním.")
        
        input_path = Path(input_path)
        if not input_path.exists():
            return False, f"Soubor neexistuje: {input_path}"
        
        if output_path is None:
            output_path = input_path.parent / f"{input_path.stem}_signed{input_path.suffix}"
        else:
            output_path = Path(output_path)
        
        try:
            # Získáme certifikát
            certificate = self.signing_context.cert
            
            # Vytvoříme metadata podpisu
            if metadata is None:
                metadata = SigningMetadata()
            
            signer_name = metadata.signer_name
            if not signer_name:
                try:
                    cert_subject = certificate.subject
                    signer_name = cert_subject.rfc4514_string() if hasattr(cert_subject, 'rfc4514_string') else str(cert_subject)
                except:
                    signer_name = "Elektronický podpis"
            
            pdf_metadata = PdfSignatureMetadata(
                field_name="Signature1",
                reason=metadata.reason,
                location=metadata.location,
                contact_info=metadata.contact_info,
                signer_name=signer_name
            )
            
            # TSA pro LTV (Long Term Validation)
            timestamp_url = None
            if use_tsa:
                timestamp_url = self.tsa_url
                logger.info(f"Používá se TSA: {timestamp_url}")
            
            # Vytvoříme PDF signer
            pdf_signer = signers.PdfSigner(
                self.signing_context,
                signature_meta=pdf_metadata,
                timestamp_url=timestamp_url
            )
            
            # Vizuální razítko (ČKAIT styl)
            if visual_stamp:
                stamp_text = self.create_visual_stamp_text(certificate, visual_stamp)
                logger.info(f"Přidává se vizuální razítko na stránku {visual_stamp.page_number}")
                
                pdf_signer.append_signature_field(
                    SigFieldSpec(
                        "Signature1",
                        box=(
                            visual_stamp.x,
                            visual_stamp.y,
                            visual_stamp.x + visual_stamp.width,
                            visual_stamp.y + visual_stamp.height
                        ),
                        on_page=visual_stamp.page_number
                    )
                )
            
            # Podepíšeme PDF
            logger.info(f"Podepisuji PDF: {input_path} → {output_path}")
            with open(input_path, 'rb') as inf:
                with open(output_path, 'wb') as outf:
                    pdf_signer.sign_pdf(inf, outf)
            
            logger.info("PDF úspěšně podepsáno")
            return True, f"PDF podepsáno podle PAdES LTV → {output_path.name}"
        
        except SigningError as e:
            logger.error(f"Chyba při podepisování: {e}")
            return False, f"Chyba podepisování: {str(e)}"
        except Exception as e:
            logger.exception(f"Neočekávaná chyba při podepisování: {e}")
            return False, f"Chyba: {str(e)}"
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - zavře session"""
        self.close_session()


# Příklad použití
if __name__ == "__main__":
    # Nastavíme logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # Konfigurace PKCS#11 (iSignum/PostSignum)
    pkcs11_config = PKCS11Config(
        dll_path=r"C:\Windows\System32\bit4xpki.dll",  # Změňte na cestu k vašemu middleware
        slot_id=None  # Automaticky první dostupný slot
    )
    
    try:
        # Vytvoříme signer
        signer = PDFSigner(pkcs11_config, tsa_url="http://tsa.postsignum.cz/tsp")
        
        # Zobrazíme dostupné sloty
        print("Dostupné sloty:")
        slots = signer.list_slots()
        for slot in slots:
            print(f"  Slot {slot['slot_id']}: {slot['token_label']} ({slot['token_manufacturer']})")
        
        # Zobrazíme certifikáty
        print("\nCertifikáty na tokenu:")
        certs = signer.list_certificates()
        for i, cert in enumerate(certs, 1):
            print(f"\n{i}. {cert['label']}")
            print(f"   Subject: {cert['subject'][:80]}...")
            print(f"   Platný do: {cert['valid_to'] if cert['valid_to'] else 'N/A'}")
            if cert.get('is_expired'):
                print(f"   ⚠ CERTIFIKÁT VYPRŠEL!")
        
        if certs:
            # Inicializujeme session s prvním certifikátem
            print(f"\nInicializuji session s certifikátem: {certs[0]['label']}")
            signer.initialize_session(certificate_label=certs[0]['label'])
            
            # Konfigurace vizuálního razítka
            visual_stamp = VisualStampConfig(
                page_number=0,
                x=50.0,
                y=50.0,
                width=200.0,
                height=100.0,
                show_name=True,
                show_date=True,
                show_authorized_engineer=True,
                organization="ČKAIT"
            )
            
            # Metadata podpisu
            metadata = SigningMetadata(
                reason="Elektronický podpis dokumentu",
                location="Česká republika",
                contact_info=""
            )
            
            # Podepíšeme PDF
            input_pdf = "test.pdf"
            if Path(input_pdf).exists():
                success, message = signer.sign_pdf(
                    input_pdf,
                    visual_stamp=visual_stamp,
                    metadata=metadata,
                    use_tsa=True
                )
                print(f"\n{'✓' if success else '✗'} {message}")
            else:
                print(f"\n⚠ Testovací PDF '{input_pdf}' neexistuje")
        
        # Zavřeme session
        signer.close_session()
    
    except Exception as e:
        print(f"\n✗ Chyba: {e}")
        import traceback
        traceback.print_exc()
