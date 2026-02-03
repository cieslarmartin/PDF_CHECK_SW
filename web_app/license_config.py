# license_config.py
# Centrální konfigurace licenčního systému
# Build 41 | © 2025 Ing. Martin Cieślar
#
# TENTO SOUBOR JE JEDINÝ ZDROJ PRAVDY PRO LICENCE
# Při přidávání nových funkcí stačí upravit tento soubor

from enum import IntEnum
from typing import Dict, List, Any
import time
import hashlib
import hmac

# =============================================================================
# LICENCE TIERS (úrovně) – podle cenové politiky: Free, Basic, Pro (+ Trial v DB)
# Basic = PROJEKTANT (1290 Kč/rok), Pro = VEDOUCÍ PROJEKTANT (1990 Kč/rok)
# ENTERPRISE = zachován pro zpětnou kompatibilitu, chová se jako Pro
# =============================================================================

class LicenseTier(IntEnum):
    """Úrovně licencí - číslo určuje prioritu"""
    FREE = 0
    BASIC = 1
    PRO = 2
    ENTERPRISE = 3  # Zpětná kompatibilita; na serveru nepoužívat, = Pro


# Názvy tierů pro zobrazení (v aplikaci a adminu)
TIER_NAMES = {
    LicenseTier.FREE: "Free",
    LicenseTier.BASIC: "Basic",
    LicenseTier.PRO: "Pro",
    LicenseTier.ENTERPRISE: "Pro",  # Zobrazit jako Pro
}

# Barvy tierů pro UI
TIER_COLORS = {
    LicenseTier.FREE: "#6b7280",      # Gray
    LicenseTier.BASIC: "#3b82f6",     # Blue
    LicenseTier.PRO: "#8b5cf6",       # Purple
    LicenseTier.ENTERPRISE: "#f59e0b" # Gold
}


# =============================================================================
# FEATURE FLAGS – podle cenové politiky: Basic (PROJEKTANT) vs Pro (VEDOUCÍ PROJEKTANT)
# Basic: kontrola PDF, podpisy, 100 souborů/dávka, BEZ exportu Excel.
# Pro: vše + export Excel/CSV, vyšší limity, 3 zařízení.
# =============================================================================

class Feature:
    """Definice feature flagu"""

    # Základní (Free, Basic, Pro)
    PDF_CHECK = "pdf_check"
    SIGNATURE_CHECK = "signature_check"

    # Basic: 100 souborů, bez exportu Excel
    BATCH_UPLOAD = "batch_upload"
    DETAILED_VIEW = "detailed_view"
    HISTORY_30_DAYS = "history_30_days"

    # Jen Pro: export Excel/CSV, vyšší limity
    EXPORT_EXCEL = "export_excel"
    EXPORT_CSV = "export_csv"
    BATCH_UNLIMITED = "batch_unlimited"
    EXPORT_ALL = "export_all"
    TREE_STRUCTURE = "tree_structure"
    TSA_FILTER = "tsa_filter"
    ADVANCED_FILTERS = "advanced_filters"
    API_ACCESS = "api_access"
    HISTORY_90_DAYS = "history_90_days"

    # Enterprise = Pro (zpětná kompatibilita)
    MULTI_USER = "multi_user"
    MULTI_DEVICE = "multi_device"
    PRIORITY_SUPPORT = "priority_support"
    CUSTOM_BRANDING = "custom_branding"
    HISTORY_UNLIMITED = "history_unlimited"


# Mapování funkcí na tiery (Free | Basic | Pro; ENTERPRISE = stejné jako Pro)
FEATURE_TIERS: Dict[str, List[LicenseTier]] = {
    Feature.PDF_CHECK: [LicenseTier.FREE, LicenseTier.BASIC, LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.SIGNATURE_CHECK: [LicenseTier.FREE, LicenseTier.BASIC, LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.BATCH_UPLOAD: [LicenseTier.BASIC, LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.DETAILED_VIEW: [LicenseTier.BASIC, LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.HISTORY_30_DAYS: [LicenseTier.BASIC, LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.EXPORT_EXCEL: [LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.EXPORT_CSV: [LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.BATCH_UNLIMITED: [LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.EXPORT_ALL: [LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.TREE_STRUCTURE: [LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.TSA_FILTER: [LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.ADVANCED_FILTERS: [LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.API_ACCESS: [LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.HISTORY_90_DAYS: [LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.MULTI_USER: [LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.MULTI_DEVICE: [LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.PRIORITY_SUPPORT: [LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.CUSTOM_BRANDING: [LicenseTier.PRO, LicenseTier.ENTERPRISE],
    Feature.HISTORY_UNLIMITED: [LicenseTier.PRO, LicenseTier.ENTERPRISE],
}


# =============================================================================
# LIMITY – podle cenové politiky (Basic 1290 Kč, Pro 1990 Kč)
# Free: 5 souborů, 1 zařízení. Basic: 100 souborů, 1 zařízení, bez Excel.
# Pro: neomezeno / vysoké limity, 3 zařízení, export Excel.
# =============================================================================

TIER_LIMITS: Dict[LicenseTier, Dict[str, Any]] = {
    LicenseTier.FREE: {
        'max_files_per_batch': 5,
        'max_file_size_mb': 10,
        'max_batches_stored': 1,
        'history_days': 1,
        'max_devices': 1,
        'rate_limit_per_hour': 3,
        'can_use_agent': False,
    },
    LicenseTier.BASIC: {
        'max_files_per_batch': 100,
        'max_file_size_mb': 50,
        'max_batches_stored': 10,
        'history_days': 30,
        'max_devices': 1,
        'rate_limit_per_hour': 100,
        'can_use_agent': True,
    },
    LicenseTier.PRO: {
        'max_files_per_batch': -1,
        'max_file_size_mb': 100,
        'max_batches_stored': 50,
        'history_days': 90,
        'max_devices': 3,
        'rate_limit_per_hour': 1000,
        'can_use_agent': True,
    },
    # Enterprise = stejné jako Pro (zpětná kompatibilita)
    LicenseTier.ENTERPRISE: {
        'max_files_per_batch': -1,
        'max_file_size_mb': 100,
        'max_batches_stored': 50,
        'history_days': 90,
        'max_devices': 3,
        'rate_limit_per_hour': 1000,
        'can_use_agent': True,
    },
}


# =============================================================================
# JWT KONFIGURACE
# =============================================================================

# DŮLEŽITÉ: V produkci nahradit silným náhodným klíčem!
JWT_SECRET = "pdfcheck_jwt_secret_change_in_production_2025"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24  # Token platí 24 hodin


# =============================================================================
# HELPER FUNKCE
# =============================================================================

def get_tier_features(tier: LicenseTier) -> List[str]:
    """Vrátí seznam funkcí dostupných pro daný tier"""
    features = []
    for feature, tiers in FEATURE_TIERS.items():
        if tier in tiers:
            features.append(feature)
    return features


def get_tier_limits(tier: LicenseTier) -> Dict[str, Any]:
    """Vrátí limity pro daný tier"""
    return TIER_LIMITS.get(tier, TIER_LIMITS[LicenseTier.FREE])


def has_feature(tier: LicenseTier, feature: str) -> bool:
    """Zkontroluje zda tier má přístup k funkci"""
    allowed_tiers = FEATURE_TIERS.get(feature, [])
    return tier in allowed_tiers


def get_limit(tier: LicenseTier, limit_name: str) -> Any:
    """Vrátí konkrétní limit pro tier"""
    limits = get_tier_limits(tier)
    return limits.get(limit_name, 0)


def tier_from_string(tier_str: str) -> LicenseTier:
    """Převede string na LicenseTier"""
    tier_map = {
        'free': LicenseTier.FREE,
        'basic': LicenseTier.BASIC,
        'pro': LicenseTier.PRO,
        'enterprise': LicenseTier.ENTERPRISE,
    }
    return tier_map.get(tier_str.lower(), LicenseTier.FREE)


def tier_to_string(tier: LicenseTier) -> str:
    """Převede LicenseTier na string"""
    return TIER_NAMES.get(tier, "Free")


# =============================================================================
# JWT TOKEN GENEROVÁNÍ A VALIDACE
# =============================================================================

def create_license_token(api_key: str, tier: LicenseTier, hwid: str = None,
                         user_name: str = None) -> str:
    """
    Vytvoří podepsaný license token (jednoduchý JWT-like formát)

    Token obsahuje:
    - api_key: API klíč uživatele
    - tier: úroveň licence
    - features: seznam povolených funkcí
    - limits: limity pro daný tier
    - hwid: hardware ID (pokud je binding)
    - exp: čas expirace
    - iat: čas vydání
    """
    import base64
    import json

    now = int(time.time())
    exp = now + (JWT_EXPIRATION_HOURS * 3600)

    payload = {
        'api_key': api_key,
        'tier': int(tier),
        'tier_name': tier_to_string(tier),
        'features': get_tier_features(tier),
        'limits': get_tier_limits(tier),
        'hwid': hwid,
        'user_name': user_name,
        'iat': now,
        'exp': exp,
    }

    # Encode payload
    payload_json = json.dumps(payload, separators=(',', ':'))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip('=')

    # Create signature
    signature = hmac.new(
        JWT_SECRET.encode(),
        payload_b64.encode(),
        hashlib.sha256
    ).hexdigest()

    # Token = payload.signature
    return f"{payload_b64}.{signature}"


def validate_license_token(token: str) -> Dict[str, Any]:
    """
    Validuje license token a vrátí payload

    Returns:
        Dict s payload daty nebo {'valid': False, 'error': 'message'}
    """
    import base64
    import json

    try:
        parts = token.split('.')
        if len(parts) != 2:
            return {'valid': False, 'error': 'Invalid token format'}

        payload_b64, signature = parts

        # Verify signature
        expected_sig = hmac.new(
            JWT_SECRET.encode(),
            payload_b64.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            return {'valid': False, 'error': 'Invalid signature'}

        # Decode payload
        # Add padding if needed
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding

        payload_json = base64.urlsafe_b64decode(payload_b64).decode()
        payload = json.loads(payload_json)

        # Check expiration
        if payload.get('exp', 0) < time.time():
            return {'valid': False, 'error': 'Token expired'}

        payload['valid'] = True
        return payload

    except Exception as e:
        return {'valid': False, 'error': str(e)}


# =============================================================================
# PERMISSIONS MASK (pro kompaktní přenos)
# =============================================================================

def features_to_mask(features: List[str]) -> int:
    """Převede seznam funkcí na bitovou masku"""
    all_features = list(FEATURE_TIERS.keys())
    mask = 0
    for i, feature in enumerate(all_features):
        if feature in features:
            mask |= (1 << i)
    return mask


def mask_to_features(mask: int) -> List[str]:
    """Převede bitovou masku na seznam funkcí"""
    all_features = list(FEATURE_TIERS.keys())
    features = []
    for i, feature in enumerate(all_features):
        if mask & (1 << i):
            features.append(feature)
    return features


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=== License Config Test ===\n")

    # Test tier features
    for tier in LicenseTier:
        features = get_tier_features(tier)
        limits = get_tier_limits(tier)
        print(f"{tier_to_string(tier)}:")
        print(f"  Features ({len(features)}): {', '.join(features[:3])}...")
        print(f"  Max files/batch: {limits['max_files_per_batch']}")
        print(f"  Can use agent: {limits['can_use_agent']}")
        print()

    # Test token
    print("=== Token Test ===")
    token = create_license_token("sk_test_abc123", LicenseTier.PRO, "HWID123", "Test User")
    print(f"Token: {token[:50]}...")

    validated = validate_license_token(token)
    print(f"Valid: {validated.get('valid')}")
    print(f"Tier: {validated.get('tier_name')}")
    print(f"Features: {len(validated.get('features', []))} features")
