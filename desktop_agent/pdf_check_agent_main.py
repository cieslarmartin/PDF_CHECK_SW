# pdf_check_agent_main.py
# PDF DokuCheck Desktop Agent - Hlavní soubor
# Build 1.1 - Aktivace licence (dialog Licence / Přihlášení, zobrazení účtu)
# © 2025 Ing. Martin Cieślar

import os
import sys
import logging
from pathlib import Path
import requests

# Importy lokálních modulů
from pdf_checker import analyze_pdf_file, analyze_multiple_pdfs, analyze_folder
from license import LicenseManager
# Grafika V3 (Enterprise) – strom složek, světlé rozlišení, bez detailu kontroly v okně
from ui_2026_v3_enterprise import create_app_2026_v3 as create_app


def _get_base_path():
    """Cesta k složce s exe (při distribuci) nebo ke skriptu (při vývoji)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _get_user_data_dir():
    """
    Při běhu z exe (např. z Program Files): vrací zapisovatelnou složku uživatele,
    aby aplikace nemusela zapisovat do Program Files (Permission denied).
    Jinak vrací base_path.
    """
    if not getattr(sys, 'frozen', False):
        return _get_base_path()
    # Windows: APPDATA\PDF DokuCheck Agent (nebo LOCALAPPDATA)
    appdata = os.environ.get('APPDATA') or os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    user_dir = os.path.join(appdata, 'PDF DokuCheck Agent')
    try:
        os.makedirs(user_dir, exist_ok=True)
    except OSError:
        user_dir = os.path.join(os.path.expanduser('~'), 'PDF_DokuCheck_Agent')
        os.makedirs(user_dir, exist_ok=True)
    return user_dir


def _get_config_path():
    """Cesta k config.yaml – při exe z Program Files používáme zapisovatelnou složku uživatele."""
    if getattr(sys, 'frozen', False):
        return os.path.join(_get_user_data_dir(), 'config.yaml')
    return os.path.join(_get_base_path(), 'config.yaml')


def _ensure_config_in_exe_dir():
    """
    Při běhu z exe: zajistí, že v uživatelské složce existuje config.yaml.
    Zkopíruje z instalační složky (Program Files) nebo z balíčku, pokud tam ještě není.
    """
    if not getattr(sys, 'frozen', False):
        return
    config_dest = _get_config_path()
    if os.path.exists(config_dest):
        return
    try:
        import shutil
        base = _get_base_path()
        config_in_install = os.path.join(base, 'config.yaml')
        if os.path.exists(config_in_install):
            shutil.copy2(config_in_install, config_dest)
            return
        bundled = getattr(sys, '_MEIPASS', None)
        if bundled:
            default_cfg = os.path.join(bundled, 'config.bez_klice.yaml')
            if os.path.exists(default_cfg):
                shutil.copy2(default_cfg, config_dest)
    except Exception:
        pass


# Nastavení logování – při exe zapisujeme do uživatelské složky (ne do Program Files)
_base_path = _get_base_path()
_log_dir = _get_user_data_dir() if getattr(sys, 'frozen', False) else _base_path
_log_file = os.path.join(_log_dir, 'agent.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(_log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PDFCheckAgent:
    """Hlavní třída desktop agenta"""

    def __init__(self):
        _ensure_config_in_exe_dir()
        config_path = _get_config_path()
        self.license_manager = LicenseManager(config_path)
        self.root = None
        self.app = None

        logger.info("PDF DokuCheck Agent spuštěn")

    def check_pdf(self, filepath_or_folder, mode='single', auto_send=None):
        """
        Zkontroluje PDF soubor(y) a volitelně odešle výsledky.

        Args:
            filepath_or_folder: Cesta k souboru, list souborů, nebo složka
            mode: 'single', 'multiple', 'folder'
            auto_send: True = odešli na API (default z config), False = neposílat (pro sběr do jednoho batch)
        """
        do_send = auto_send if auto_send is not None else self.license_manager.get_auto_send_setting()
        try:
            if mode == 'single':
                # Jeden soubor
                logger.info(f"Kontrola souboru: {filepath_or_folder}")
                result = self._check_single_file(filepath_or_folder)

                # Odeslání na API
                if do_send and result.get('success'):
                    self.send_results_to_api(result)

                return result

            elif mode == 'multiple':
                # Více souborů
                filepaths = filepath_or_folder
                logger.info(f"Kontrola {len(filepaths)} souborů")

                # Progress callback
                def progress_callback(current, total, filename):
                    if self.app:
                        self.app.root.after(0, lambda: self.app.update_progress(current, total, filename))

                results = analyze_multiple_pdfs(filepaths, progress_callback)

                # Odeslání na API (batch)
                if do_send:
                    self.send_batch_results_to_api(results)

                return {
                    'mode': 'multiple',
                    'total': len(results),
                    'results': results
                }

            elif mode == 'folder':
                # Celá složka
                folder = filepath_or_folder
                logger.info(f"Kontrola složky: {folder}")

                # Progress callback
                def progress_callback(current, total, filename):
                    if self.app:
                        self.app.root.after(0, lambda: self.app.update_progress(current, total, filename))

                folder_results = analyze_folder(folder, progress_callback)

                # Odeslání na API (batch) - předej source_folder pro stromovou strukturu
                if do_send:
                    self.send_batch_results_to_api(folder_results.get('results', []), folder)

                return folder_results

        except Exception as e:
            logger.exception(f"Chyba při kontrole PDF: {e}")
            return {'success': False, 'error': str(e)}

    def _check_single_file(self, filepath):
        """Zkontroluje jeden PDF soubor"""
        if not os.path.exists(filepath):
            logger.error(f"Soubor neexistuje: {filepath}")
            return {'success': False, 'error': 'Soubor neexistuje'}

        if not filepath.lower().endswith('.pdf'):
            logger.error(f"Soubor není PDF: {filepath}")
            return {'success': False, 'error': 'Soubor není PDF'}

        result = analyze_pdf_file(filepath)

        if not result.get('success'):
            logger.error(f"Chyba analýzy: {result.get('error')}")
        else:
            logger.info(f"Analýza dokončena: {result.get('file_name')}")

        return result

    def send_results_to_api(self, result):
        """Odešle jeden výsledek na API server (jako batch o 1 souboru, se stromovou cestou)."""
        try:
            if not self.license_manager.has_valid_key():
                logger.warning("API klíč není nastaven, výsledky nebudou odeslány")
                return

            # Aby web zobrazil strom i u jednoho souboru
            if 'folder' not in result:
                result['folder'] = '.'
            if 'relative_path' not in result:
                result['relative_path'] = result.get('file_name', '')

            logger.info("Odesílám výsledky na server...")
            self.send_batch_results_to_api([result], source_folder=None)

        except Exception as e:
            logger.exception(f"Chyba při odesílání výsledků: {e}")

    def send_batch_results_to_api(self, results, source_folder=None):
        """Odešle CELÝ batch najednou v jednom requestu. Vrátí (success, message, batch_id, response_data)."""
        try:
            if not self.license_manager.has_valid_key():
                logger.warning("API klíč není nastaven, výsledky nebudou odeslány")
                return False, "API klíč není nastaven", None, None

            from datetime import datetime
            import os

            # Název batch = název složky + datum
            if source_folder:
                folder_name = os.path.basename(source_folder)
                batch_name = f"{folder_name} ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
            else:
                batch_name = f"PDF Check ({datetime.now().strftime('%Y-%m-%d %H:%M')})"

            logger.info(f"Odesílám {len(results)} výsledků na server (jeden request)...")

            # Odešli VŠECHNO najednou (vrací response_data pro partial handling v UI)
            out = self.license_manager.upload_batch(batch_name, source_folder, results)
            success = out[0]
            message = out[1]
            batch_id = out[2]
            response_data = out[3] if len(out) > 3 else None

            if success:
                logger.info(f"Batch úspěšně odeslán: {batch_id} - {message}")
                if response_data and response_data.get('status') == 'partial':
                    logger.info(f"Částečný batch: {response_data.get('message', '')}")
            else:
                logger.error(f"Chyba při odesílání batch: {message}")

            return success, message, batch_id, response_data

        except Exception as e:
            logger.exception(f"Chyba při odesílání batch výsledků: {e}")
            return False, str(e), None, None

    def verify_api_key(self, api_key):
        """Ověří API klíč u serveru, uloží ho a vrátí (success, message, display_text pro UI)."""
        logger.info("Ověřuji API klíč...")
        success, message = self.license_manager.verify_api_key(api_key)
        if success:
            if not self.license_manager.save_api_key(api_key):
                logger.error("Nepodařilo se uložit API klíč")
                return False, "Nepodařilo se uložit API klíč", None
            logger.info("API klíč uložen")
            ok, info = self.license_manager.get_license_info(api_key)
            display_text = None
            if ok and info:
                email = info.get("email") or info.get("user_name") or "—"
                tier = info.get("tier_name") or "—"
                display_text = f"{email} ({tier})"
            return True, "Licence aktivována a uložena.", display_text
        logger.warning(f"API klíč není platný: {message}")
        return False, message, None

    def login_with_password(self, email, password):
        """Přihlášení e-mailem a heslem. Vrátí (success, message, display_text) pro UI."""
        logger.info("Přihlášení e-mailem a heslem...")
        success, api_key, display_or_err = self.license_manager.login_with_password(email, password)
        if success:
            logger.info("Přihlášeno.")
            return True, "Přihlášeno.", display_or_err
        logger.warning(f"Přihlášení selhalo: {display_or_err}")
        return False, display_or_err, None

    def _clear_view(self):
        """Vymaže frontu úkolů a zobrazené výsledky (po přihlášení/odhlášení)."""
        if self.app:
            self.app.clear_results_and_queue()

    def logout(self):
        """Odhlášení – vymaže zobrazení a klíč. Přihlášení jen ručně tlačítkem."""
        if self.app:
            self.app.clear_results_and_queue()
        self.license_manager.clear_api_key()
        if self.app:
            self.app.set_license_display("")

    def get_max_files_for_batch(self):
        """Vrátí max. počet souborů v dávce dle licence (Free=5, Basic+=dle limitu, -1=neomezeno)."""
        if not self.license_manager.has_valid_key():
            return 5
        ok, info = self.license_manager.get_license_info()
        if not ok or not info:
            return 5
        limits = info.get("limits") or {}
        max_f = limits.get("max_files_per_batch", 5)
        return max_f if max_f is not None and max_f >= 0 else 99999

    def _refresh_license_display(self):
        """Načte údaje o licenci a zobrazí je (Přihlášen: email (Tier) nebo Trial verze – Limit X souborů)."""
        if not self.app or not self.license_manager.has_valid_key():
            if self.app and hasattr(self.app, 'set_export_xls_enabled'):
                self.app.set_export_xls_enabled(False)
            return
        ok, info = self.license_manager.get_license_info()
        if ok and info:
            tier_name = (info.get("tier_name") or "").strip()
            if tier_name.lower() == "trial":
                self.app.set_license_display("Režim: Zkušební verze (Trial)")
            else:
                email = info.get("email") or info.get("user_name") or "—"
                tier = info.get("tier_name") or "—"
                self.app.set_license_display(f"{email} ({tier})")
            allow_excel = info.get("allow_excel_export") or (tier_name.lower() == "pro")
            if hasattr(self.app, 'set_export_xls_enabled'):
                self.app.set_export_xls_enabled(bool(allow_excel))
            used = info.get("daily_files_used", 0)
            limit = (info.get("limits") or {}).get("daily_files_limit") or info.get("daily_files_limit")
            if hasattr(self.app, 'set_daily_limit_display'):
                self.app.set_daily_limit_display(used, limit)
        else:
            self.app.set_license_display("")
            if hasattr(self.app, 'set_export_xls_enabled'):
                self.app.set_export_xls_enabled(False)

    def check_first_run(self):
        """Zkontroluje, zda je nastaven platný klíč. Přihlášení se vyvolá pouze ručně tlačítkem."""
        if not self.license_manager.has_valid_key():
            logger.info("První spuštění – licence není aktivována (přihlášení přes tlačítko v sidebaru)")
            return True
        # Ověř klíč se serverem
        logger.info("Ověřuji licenci se serverem...")
        success, _ = self.license_manager.verify_api_key()
        if not success:
            logger.warning("Licence není platná – přihlaste se znovu v sidebaru")
        return False

    def run(self):
        """Spustí agenta"""
        logger.info("Spouštím GUI...")

        def _get_remote_config():
            rc = getattr(self.license_manager, 'remote_config', None)
            return rc if isinstance(rc, dict) else self.license_manager._get_default_config()

        # Vytvoř GUI (api_url, přihlášení, odhlášení, limit souborů, odeslání batch s vrácením response)
        self.root, self.app = create_app(
            on_check_callback=self.check_pdf,
            on_api_key_callback=self.verify_api_key,
            api_url=self.license_manager.api_url,
            on_login_password_callback=self.login_with_password,
            on_logout_callback=self.logout,
            on_get_max_files=self.get_max_files_for_batch,
            on_after_login_callback=self._clear_view,
            on_after_logout_callback=self._clear_view,
            on_get_web_login_url=lambda: self._get_web_login_url(),
            on_send_batch_callback=lambda results, src=None: self.send_batch_results_to_api(results, src),
            on_has_login=lambda: self.license_manager.has_valid_key(),
            on_get_remote_config=_get_remote_config,
        )

        # Zkontroluj první spuštění a zobraz stav licence
        self.check_first_run()
        self._refresh_license_display()

        # Spusť hlavní smyčku
        logger.info("Agent běží")
        self.root.mainloop()

        logger.info("Agent ukončen")

    def _get_web_login_url(self):
        """
        Získá od serveru jednorázový přihlašovací odkaz (s tokenem).
        Po otevření v prohlížeči se uživatel na webu automaticky přihlásí.
        Vrací URL nebo None při chybě / nepřihlášení.
        """
        if not self.license_manager.has_valid_key():
            return None
        api_key = self.license_manager.api_key
        base_url = (self.license_manager.api_url or "").rstrip("/")
        if not base_url:
            return None
        try:
            r = requests.post(
                base_url + "/api/auth/one-time-login-token",
                headers={"Authorization": "Bearer " + api_key},
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("success") and data.get("login_url"):
                    return data["login_url"]
        except Exception:
            pass
        return None


def main():
    """Hlavní entry point"""
    try:
        agent = PDFCheckAgent()
        agent.run()
    except KeyboardInterrupt:
        logger.info("Agent ukončen uživatelem")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Kritická chyba: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
