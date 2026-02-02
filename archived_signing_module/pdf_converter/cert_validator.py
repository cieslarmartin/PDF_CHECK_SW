# cert_validator.py
# Validace certifikátů pro podepisování
# Build 2.0 | © 2025 Ing. Martin Cieślar

import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# POVINNÉ: pyhanko musí být nainstalován
try:
    from pyhanko.sign import signers
    from pyhanko.sign.signers.pdf_cms import signer_from_p12_config, PKCS12SignatureConfig
    PYHANKO_AVAILABLE = True
except ImportError as e:
    PYHANKO_AVAILABLE = False
    raise ImportError(
        "pyhanko není nainstalován! Validace certifikátů vyžaduje pyhanko.\n"
        "Instalujte: pip install pyhanko pyhanko-certvalidator"
    ) from e

def verify_certificate(pfx_path: str, password: Optional[str] = None) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Ověří .pfx certifikát a vrátí informace o něm.
    
    Args:
        pfx_path: Cesta k .pfx/.p12 souboru
        password: Heslo pro .pfx soubor (None = zkusí bez hesla)
    
    Returns:
        Tuple (success, cert_info, error_message)
        cert_info: {
            'common_name': str,
            'subject': str,
            'issuer': str,
            'expiration_date': datetime,
            'serial_number': str,
            'signer_obj': Any  # pyHanko signer objekt
        }
    """
    # pyHanko je POVINNÉ - kontrola byla provedena při importu
    if not PYHANKO_AVAILABLE:
        raise ImportError("pyhanko není nainstalován. Instalujte: pip install pyhanko pyhanko-certvalidator")
    
    pfx_path = Path(pfx_path)
    if not pfx_path.exists():
        return False, None, "Soubor neexistuje"
    
    try:
        # Připravíme heslo - pokud je prázdné nebo None, zkusíme bez hesla
        pfx_passphrase_bytes = None
        if password and len(password) >= 1:
            pfx_passphrase_bytes = password.encode() if isinstance(password, str) else password
        
        # Zkusíme načíst certifikát pomocí pyHanko
        signer_obj = None
        cert_info = {}
        
        # Zkusíme s různými hesly (zadané, žádné, prázdné)
        for test_pwd in [pfx_passphrase_bytes, None, b""]:
            try:
                p12_config = PKCS12SignatureConfig(
                    pfx_file=str(pfx_path),
                    pfx_passphrase=test_pwd
                )
                signer_obj = signer_from_p12_config(p12_config)
                
                # Pokud se podařilo, načteme informace o certifikátu
                if signer_obj:
                    # Získáme certifikát z signer objektu
                    try:
                        from cryptography.hazmat.primitives.serialization import pkcs12
                        from cryptography.hazmat.backends import default_backend
                        from cryptography import x509
                        
                        with open(pfx_path, 'rb') as f:
                            pfx_data = f.read()
                        
                        _, cert, _ = pkcs12.load_key_and_certificates(
                            pfx_data,
                            test_pwd,
                            backend=default_backend()
                        )
                        
                        if cert:
                            # Získáme Common Name
                            common_name = None
                            try:
                                for attr in cert.subject:
                                    if hasattr(attr, 'oid'):
                                        if attr.oid._name == 'commonName':
                                            common_name = attr.value
                                            break
                                if not common_name:
                                    # Zkusíme z rfc4514_string
                                    subject_str = cert.subject.rfc4514_string() if hasattr(cert.subject, 'rfc4514_string') else str(cert.subject)
                                    if 'CN=' in subject_str:
                                        common_name = subject_str.split('CN=')[1].split(',')[0].strip()
                            except:
                                common_name = "Neznámé"
                            
                            # Použijeme not_valid_after_utc místo not_valid_after (deprecated)
                            expiration_date = cert.not_valid_after_utc if hasattr(cert, 'not_valid_after_utc') else cert.not_valid_after
                            
                            cert_info = {
                                'common_name': common_name or "Neznámé",
                                'subject': cert.subject.rfc4514_string() if hasattr(cert.subject, 'rfc4514_string') else str(cert.subject),
                                'issuer': cert.issuer.rfc4514_string() if hasattr(cert.issuer, 'rfc4514_string') else str(cert.issuer),
                                'expiration_date': expiration_date,
                                'serial_number': hex(cert.serial_number)[2:].upper(),
                                'signer_obj': signer_obj  # Uložíme signer objekt pro pozdější použití
                            }
                            
                            return True, cert_info, None
                    except Exception as e:
                        logger.warning(f"Chyba při načítání informací o certifikátu: {e}")
                        # I když se nepodařilo načíst info, signer funguje
                        return True, {'signer_obj': signer_obj}, None
                
                break
            except Exception as e:
                if "password" in str(e).lower() or "invalid" in str(e).lower():
                    continue  # Zkusíme další heslo
                else:
                    logger.warning(f"Chyba při načítání certifikátu: {e}")
                    continue
        
        # Pokud jsme se sem dostali, certifikát se nepodařilo načíst
        return False, None, "Špatné heslo nebo poškozený soubor"
        
    except Exception as e:
        logger.exception(f"Chyba při ověřování certifikátu: {e}")
        return False, None, f"Chyba při ověřování: {str(e)}"

