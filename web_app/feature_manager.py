# feature_manager.py
# Feature Manager pro PDF DokuCheck - kontrola oprávnění
# Build 41 | © 2025 Ing. Martin Cieślar
#
# Tento modul poskytuje jednotné rozhraní pro kontrolu feature flags
# Používá se jak ve webovém rozhraní, tak v desktop agentovi

from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Import konfigurace
try:
    from license_config import (
        LicenseTier, Feature, FEATURE_TIERS, TIER_LIMITS,
        has_feature, get_limit, get_tier_features, get_tier_limits,
        tier_from_string, tier_to_string, TIER_NAMES, TIER_COLORS,
        validate_license_token, create_license_token
    )
except ImportError:
    # Fallback pro standalone použití
    class LicenseTier:
        FREE = 0
        BASIC = 1
        PRO = 2
        ENTERPRISE = 3


@dataclass
class LicenseContext:
    """Kontext licence pro aktuálního uživatele/session"""
    tier: int = 0
    tier_name: str = "Free"
    features: List[str] = None
    limits: Dict[str, Any] = None
    api_key: str = None
    hwid: str = None
    user_name: str = None
    is_valid: bool = False
    is_expired: bool = False
    days_remaining: int = -1
    error: str = None

    def __post_init__(self):
        if self.features is None:
            self.features = []
        if self.limits is None:
            self.limits = {}


class FeatureManager:
    """
    Správce feature flags pro kontrolu oprávnění

    Použití:
        fm = FeatureManager(license_context)
        if fm.can_use('batch_upload'):
            # Povol batch upload
        else:
            # Zobraz upgrade dialog
    """

    def __init__(self, context: LicenseContext = None):
        """
        Inicializuje FeatureManager

        Args:
            context: LicenseContext s informacemi o licenci
                    Pokud není poskytnut, použije se FREE tier
        """
        if context:
            self.context = context
        else:
            # Default: FREE tier
            self.context = LicenseContext(
                tier=LicenseTier.FREE,
                tier_name="Free",
                features=self._get_free_features(),
                limits=self._get_free_limits(),
                is_valid=True
            )

    def _get_free_features(self) -> List[str]:
        """Vrátí features pro FREE tier"""
        try:
            return get_tier_features(LicenseTier.FREE)
        except:
            return ['pdf_check', 'signature_check']

    def _get_free_limits(self) -> Dict[str, Any]:
        """Vrátí limity pro FREE tier"""
        try:
            return get_tier_limits(LicenseTier.FREE)
        except:
            return {
                'max_files_per_batch': 5,
                'max_file_size_mb': 10,
                'rate_limit_per_hour': 3,
                'can_use_agent': False
            }

    @classmethod
    def from_token(cls, token: str) -> 'FeatureManager':
        """
        Vytvoří FeatureManager z license tokenu

        Args:
            token: JWT-like license token

        Returns:
            FeatureManager instance
        """
        try:
            payload = validate_license_token(token)

            if not payload.get('valid'):
                return cls(LicenseContext(
                    is_valid=False,
                    error=payload.get('error', 'Invalid token')
                ))

            context = LicenseContext(
                tier=payload.get('tier', 0),
                tier_name=payload.get('tier_name', 'Free'),
                features=payload.get('features', []),
                limits=payload.get('limits', {}),
                api_key=payload.get('api_key'),
                hwid=payload.get('hwid'),
                user_name=payload.get('user_name'),
                is_valid=True
            )

            return cls(context)

        except Exception as e:
            return cls(LicenseContext(
                is_valid=False,
                error=str(e)
            ))

    @classmethod
    def from_tier(cls, tier: int) -> 'FeatureManager':
        """
        Vytvoří FeatureManager pro daný tier

        Args:
            tier: Číslo tieru (0-3)

        Returns:
            FeatureManager instance
        """
        try:
            tier_enum = LicenseTier(tier)
            context = LicenseContext(
                tier=tier,
                tier_name=tier_to_string(tier_enum),
                features=get_tier_features(tier_enum),
                limits=get_tier_limits(tier_enum),
                is_valid=True
            )
            return cls(context)
        except:
            return cls()  # Fallback to FREE

    # =========================================================================
    # ZÁKLADNÍ KONTROLY
    # =========================================================================

    def can_use(self, feature: str) -> bool:
        """
        Zkontroluje zda je funkce dostupná

        Args:
            feature: Název funkce (z Feature class)

        Returns:
            True pokud je funkce dostupná
        """
        if not self.context.is_valid:
            return False

        return feature in self.context.features

    def get_limit(self, limit_name: str, default: Any = 0) -> Any:
        """
        Vrátí limit pro danou funkci

        Args:
            limit_name: Název limitu
            default: Výchozí hodnota pokud limit neexistuje

        Returns:
            Hodnota limitu
        """
        return self.context.limits.get(limit_name, default)

    def is_unlimited(self, limit_name: str) -> bool:
        """Zkontroluje zda je limit neomezený (-1)"""
        limit = self.get_limit(limit_name, 0)
        return limit == -1

    # =========================================================================
    # SPECIFICKÉ FEATURE CHECKS (pro snadné použití)
    # =========================================================================

    def can_use_agent(self) -> bool:
        """Může používat desktop agenta?"""
        return self.get_limit('can_use_agent', False)

    def can_batch_upload(self) -> bool:
        """Může nahrávat soubory v dávkách?"""
        return self.can_use('batch_upload')

    def can_export_excel(self) -> bool:
        """Může exportovat do Excelu?"""
        return self.can_use('export_excel')

    def can_view_details(self) -> bool:
        """Může zobrazit detailní pohled?"""
        return self.can_use('detailed_view')

    def can_use_tree_structure(self) -> bool:
        """Může použít stromovou strukturu?"""
        return self.can_use('tree_structure')

    def can_filter_by_tsa(self) -> bool:
        """Může filtrovat podle TSA?"""
        return self.can_use('tsa_filter')

    def can_use_advanced_filters(self) -> bool:
        """Může použít pokročilé filtry?"""
        return self.can_use('advanced_filters')

    def can_use_api(self) -> bool:
        """Má přímý API přístup?"""
        return self.can_use('api_access')

    def has_unlimited_batch(self) -> bool:
        """Má neomezený batch upload?"""
        return self.can_use('batch_unlimited')

    def has_multi_device(self) -> bool:
        """Může používat více zařízení?"""
        return self.can_use('multi_device')

    # =========================================================================
    # LIMIT CHECKS
    # =========================================================================

    def get_max_files_per_batch(self) -> int:
        """Maximální počet souborů v jedné dávce"""
        limit = self.get_limit('max_files_per_batch', 5)
        return -1 if limit == -1 else limit

    def get_max_file_size_mb(self) -> int:
        """Maximální velikost souboru v MB"""
        limit = self.get_limit('max_file_size_mb', 10)
        return -1 if limit == -1 else limit

    def get_history_days(self) -> int:
        """Počet dní historie"""
        limit = self.get_limit('history_days', 1)
        return -1 if limit == -1 else limit

    def get_rate_limit_per_hour(self) -> int:
        """Rate limit za hodinu"""
        limit = self.get_limit('rate_limit_per_hour', 3)
        return -1 if limit == -1 else limit

    def get_max_devices(self) -> int:
        """Maximální počet zařízení"""
        limit = self.get_limit('max_devices', 1)
        return -1 if limit == -1 else limit

    # =========================================================================
    # VALIDACE AKCÍ
    # =========================================================================

    def check_file_size(self, size_bytes: int) -> tuple:
        """
        Zkontroluje zda je velikost souboru v limitu

        Returns:
            tuple: (allowed: bool, message: str)
        """
        max_mb = self.get_max_file_size_mb()
        if max_mb == -1:
            return True, "OK"

        size_mb = size_bytes / (1024 * 1024)
        if size_mb > max_mb:
            return False, f"Soubor je příliš velký ({size_mb:.1f} MB). Maximum pro váš tier: {max_mb} MB"

        return True, "OK"

    def check_batch_size(self, file_count: int) -> tuple:
        """
        Zkontroluje zda je počet souborů v limitu

        Returns:
            tuple: (allowed: bool, message: str)
        """
        max_files = self.get_max_files_per_batch()
        if max_files == -1:
            return True, "OK"

        if file_count > max_files:
            return False, f"Příliš mnoho souborů ({file_count}). Maximum pro váš tier: {max_files}"

        return True, "OK"

    # =========================================================================
    # UI HELPERS
    # =========================================================================

    def get_tier_info(self) -> Dict[str, Any]:
        """Vrátí informace o tieru pro zobrazení v UI"""
        tier_colors = {
            0: "#6b7280",  # Gray - Free
            1: "#3b82f6",  # Blue - Basic
            2: "#8b5cf6",  # Purple - Pro
            3: "#f59e0b"   # Gold - Enterprise
        }

        return {
            'tier': self.context.tier,
            'name': self.context.tier_name,
            'color': tier_colors.get(self.context.tier, "#6b7280"),
            'is_valid': self.context.is_valid,
            'days_remaining': self.context.days_remaining,
            'is_expired': self.context.is_expired
        }

    def get_feature_status(self, feature: str) -> Dict[str, Any]:
        """
        Vrátí status funkce pro UI (locked/unlocked)

        Returns:
            Dict s 'available', 'locked', 'required_tier'
        """
        available = self.can_use(feature)

        # Najdi minimální tier pro tuto funkci
        required_tier = None
        try:
            tiers = FEATURE_TIERS.get(feature, [])
            if tiers:
                required_tier = min(tiers)
        except:
            pass

        return {
            'feature': feature,
            'available': available,
            'locked': not available,
            'required_tier': required_tier,
            'required_tier_name': tier_to_string(LicenseTier(required_tier)) if required_tier is not None else None
        }

    def get_all_features_status(self) -> List[Dict[str, Any]]:
        """Vrátí status všech funkcí pro UI"""
        try:
            all_features = list(FEATURE_TIERS.keys())
            return [self.get_feature_status(f) for f in all_features]
        except:
            return []

    def get_upgrade_message(self, feature: str) -> str:
        """Vrátí zprávu pro upgrade dialog"""
        status = self.get_feature_status(feature)

        if status['available']:
            return None

        tier_name = status.get('required_tier_name', 'vyšší')
        return f"Tato funkce vyžaduje {tier_name} licenci. Upgradujte pro odemčení."

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Serializuje stav do dictionary"""
        return {
            'tier': self.context.tier,
            'tier_name': self.context.tier_name,
            'features': self.context.features,
            'limits': self.context.limits,
            'is_valid': self.context.is_valid,
            'is_expired': self.context.is_expired,
            'days_remaining': self.context.days_remaining,
            'user_name': self.context.user_name
        }

    def __repr__(self):
        return f"FeatureManager(tier={self.context.tier_name}, valid={self.context.is_valid})"


# =============================================================================
# FACTORY FUNKCE PRO SNADNÉ POUŽITÍ
# =============================================================================

def create_free_manager() -> FeatureManager:
    """Vytvoří FeatureManager pro FREE tier"""
    return FeatureManager.from_tier(LicenseTier.FREE)


def create_manager_from_api_key(api_key: str, hwid: str = None) -> FeatureManager:
    """
    Vytvoří FeatureManager z API klíče (vyžaduje databázi)

    Toto je hlavní factory funkce pro použití s databází
    """
    try:
        from database import Database
        db = Database()

        if hwid:
            valid, result = db.validate_device(api_key, hwid)
        else:
            result = db.get_user_license(api_key)
            valid = result is not None and result.get('is_active')

        if not valid or not result:
            return create_free_manager()

        context = LicenseContext(
            tier=result.get('license_tier', 0),
            tier_name=result.get('tier_name', 'Free'),
            features=result.get('features', []),
            limits=result.get('limits', {}),
            api_key=api_key,
            hwid=hwid,
            user_name=result.get('user_name'),
            is_valid=True,
            is_expired=result.get('is_expired', False),
            days_remaining=result.get('days_remaining', -1)
        )

        return FeatureManager(context)

    except Exception as e:
        print(f"Error creating FeatureManager: {e}")
        return create_free_manager()


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=== Feature Manager Test ===\n")

    # Test FREE tier
    print("1. FREE tier:")
    fm_free = FeatureManager.from_tier(LicenseTier.FREE)
    print(f"   Can batch upload: {fm_free.can_batch_upload()}")
    print(f"   Can use agent: {fm_free.can_use_agent()}")
    print(f"   Max files/batch: {fm_free.get_max_files_per_batch()}")
    print(f"   Rate limit: {fm_free.get_rate_limit_per_hour()}/hour")
    print()

    # Test PRO tier
    print("2. PRO tier:")
    fm_pro = FeatureManager.from_tier(LicenseTier.PRO)
    print(f"   Can batch upload: {fm_pro.can_batch_upload()}")
    print(f"   Can use agent: {fm_pro.can_use_agent()}")
    print(f"   Can use tree structure: {fm_pro.can_use_tree_structure()}")
    print(f"   Max files/batch: {fm_pro.get_max_files_per_batch()}")
    print(f"   Rate limit: {fm_pro.get_rate_limit_per_hour()}/hour")
    print()

    # Test ENTERPRISE tier
    print("3. ENTERPRISE tier:")
    fm_ent = FeatureManager.from_tier(LicenseTier.ENTERPRISE)
    print(f"   Has unlimited batch: {fm_ent.has_unlimited_batch()}")
    print(f"   Has multi-device: {fm_ent.has_multi_device()}")
    print(f"   Max files/batch: {fm_ent.get_max_files_per_batch()} (unlimited)")
    print()

    # Test file size check
    print("4. File size validation:")
    allowed, msg = fm_free.check_file_size(5 * 1024 * 1024)  # 5 MB
    print(f"   FREE - 5MB file: {allowed} - {msg}")
    allowed, msg = fm_free.check_file_size(15 * 1024 * 1024)  # 15 MB
    print(f"   FREE - 15MB file: {allowed} - {msg}")
    print()

    # Test upgrade message
    print("5. Upgrade messages:")
    msg = fm_free.get_upgrade_message('batch_upload')
    print(f"   {msg}")
    print()

    # Test token validation
    print("6. Token validation:")
    try:
        token = create_license_token("sk_test_123", LicenseTier.PRO, "HWID123", "Test User")
        fm_token = FeatureManager.from_token(token)
        print(f"   Token valid: {fm_token.context.is_valid}")
        print(f"   Tier: {fm_token.context.tier_name}")
        print(f"   Features: {len(fm_token.context.features)}")
    except Exception as e:
        print(f"   Token test skipped: {e}")
