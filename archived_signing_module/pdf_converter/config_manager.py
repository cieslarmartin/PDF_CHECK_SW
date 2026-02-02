# config_manager.py
# Správa konfigurace a profilů pro PDF Converter
# Build 1.0 | © 2025 Ing. Martin Cieślar

import json
import os
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class ConfigManager:
    """Správce konfigurace a profilů aplikace"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Inicializuje správce konfigurace.
        
        Args:
            config_file: Cesta k konfiguračnímu souboru (pokud None, použije se výchozí)
        """
        if config_file is None:
            # Výchozí umístění: stejná složka jako spuštěný skript
            app_dir = Path(__file__).parent.parent
            config_file = app_dir / "config.json"
        
        self.config_file = Path(config_file)
        self.config_data = {
            "signing_profiles": [],
            "tsa_profiles": []
        }
        self._load_config()
    
    def _load_config(self):
        """Načte konfiguraci ze souboru"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config_data = {
                        "signing_profiles": data.get("signing_profiles", []),
                        "tsa_profiles": data.get("tsa_profiles", [])
                    }
                logger.info(f"Konfigurace načtena z {self.config_file}")
            else:
                logger.info(f"Konfigurační soubor neexistuje, použije se výchozí: {self.config_file}")
        except Exception as e:
            logger.error(f"Chyba při načítání konfigurace: {e}")
            self.config_data = {
                "signing_profiles": [],
                "tsa_profiles": []
            }
    
    def _save_config(self):
        """Uloží konfiguraci do souboru"""
        try:
            # Vytvoříme složku pokud neexistuje
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Konfigurace uložena do {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Chyba při ukládání konfigurace: {e}")
            return False
    
    # === PODPISOVÉ PROFILY ===
    
    def get_signing_profiles(self) -> List[Dict[str, Any]]:
        """Vrátí seznam podpisových profilů"""
        return self.config_data.get("signing_profiles", [])
    
    def add_signing_profile(self, profile: Dict[str, Any]) -> bool:
        """
        Přidá nový podpisový profil.
        
        Args:
            profile: Slovník s klíči: name, type (pfx/token), path, username (volitelné), label (volitelné)
        
        Returns:
            True pokud úspěšné
        """
        if "name" not in profile or "type" not in profile or "path" not in profile:
            logger.error("Profil musí obsahovat name, type a path")
            return False
        
        # Zkontrolujeme, zda profil se stejným názvem už neexistuje
        existing = [p for p in self.config_data["signing_profiles"] if p.get("name") == profile["name"]]
        if existing:
            logger.warning(f"Profil s názvem '{profile['name']}' již existuje")
            return False
        
        self.config_data["signing_profiles"].append(profile)
        return self._save_config()
    
    def update_signing_profile(self, old_name: str, profile: Dict[str, Any]) -> bool:
        """
        Aktualizuje existující podpisový profil.
        
        Args:
            old_name: Původní název profilu
            profile: Nová data profilu
        
        Returns:
            True pokud úspěšné
        """
        profiles = self.config_data["signing_profiles"]
        for i, p in enumerate(profiles):
            if p.get("name") == old_name:
                profiles[i] = profile
                return self._save_config()
        
        logger.warning(f"Profil '{old_name}' nebyl nalezen")
        return False
    
    def delete_signing_profile(self, name: str) -> bool:
        """
        Smaže podpisový profil.
        
        Args:
            name: Název profilu
        
        Returns:
            True pokud úspěšné
        """
        profiles = self.config_data["signing_profiles"]
        original_count = len(profiles)
        self.config_data["signing_profiles"] = [p for p in profiles if p.get("name") != name]
        
        if len(self.config_data["signing_profiles"]) < original_count:
            return self._save_config()
        
        logger.warning(f"Profil '{name}' nebyl nalezen")
        return False
    
    def get_signing_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """Vrátí podpisový profil podle názvu"""
        for profile in self.config_data["signing_profiles"]:
            if profile.get("name") == name:
                return profile
        return None
    
    # === TSA PROFILY ===
    
    def get_tsa_profiles(self) -> List[Dict[str, Any]]:
        """Vrátí seznam TSA profilů"""
        return self.config_data.get("tsa_profiles", [])
    
    def add_tsa_profile(self, profile: Dict[str, Any]) -> bool:
        """
        Přidá nový TSA profil.
        
        Args:
            profile: Slovník s klíči: name, url, username (volitelné), password (volitelné)
        
        Returns:
            True pokud úspěšné
        """
        if "name" not in profile or "url" not in profile:
            logger.error("TSA profil musí obsahovat name a url")
            return False
        
        # Zkontrolujeme, zda profil se stejným názvem už neexistuje
        existing = [p for p in self.config_data["tsa_profiles"] if p.get("name") == profile["name"]]
        if existing:
            logger.warning(f"TSA profil s názvem '{profile['name']}' již existuje")
            return False
        
        self.config_data["tsa_profiles"].append(profile)
        return self._save_config()
    
    def update_tsa_profile(self, old_name: str, profile: Dict[str, Any]) -> bool:
        """
        Aktualizuje existující TSA profil.
        
        Args:
            old_name: Původní název profilu
            profile: Nová data profilu
        
        Returns:
            True pokud úspěšné
        """
        profiles = self.config_data["tsa_profiles"]
        for i, p in enumerate(profiles):
            if p.get("name") == old_name:
                profiles[i] = profile
                return self._save_config()
        
        logger.warning(f"TSA profil '{old_name}' nebyl nalezen")
        return False
    
    def delete_tsa_profile(self, name: str) -> bool:
        """
        Smaže TSA profil.
        
        Args:
            name: Název profilu
        
        Returns:
            True pokud úspěšné
        """
        profiles = self.config_data["tsa_profiles"]
        original_count = len(profiles)
        self.config_data["tsa_profiles"] = [p for p in profiles if p.get("name") != name]
        
        if len(self.config_data["tsa_profiles"]) < original_count:
            return self._save_config()
        
        logger.warning(f"TSA profil '{name}' nebyl nalezen")
        return False
    
    def get_tsa_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """Vrátí TSA profil podle názvu"""
        for profile in self.config_data["tsa_profiles"]:
            if profile.get("name") == name:
                return profile
        return None


# Globální instance pro snadný přístup
_config_manager = None


def get_config_manager(config_file: Optional[str] = None) -> ConfigManager:
    """Vrátí globální instanci ConfigManager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_file)
    return _config_manager
