# license.py
# Ověřování API klíče a komunikace se serverem
# Headers X-Machine-ID, X-Machine-Name pro device locking (anti-sharing)

import requests
import yaml
import os
from pathlib import Path

# Demo Trial účet pro tlačítko "Vyzkoušet zdarma" (načte se samo; stejný výstup jako placený účet)
DEMO_TRIAL_EMAIL = 'zdarma@trial.verze'
DEMO_TRIAL_PASSWORD = 'free'

try:
    from machine_id import get_machine_id, get_hostname
except ImportError:
    def get_machine_id():
        return ''
    def get_hostname():
        return os.environ.get('COMPUTERNAME', '') or os.environ.get('HOSTNAME', '') or 'unknown'


class LicenseManager:
    """Správa API klíče a ověřování se serverem"""

    def __init__(self, config_path='config.yaml'):
        self.config_path = config_path
        self.config = self.load_config()
        self.api_url = self.config.get('api', {}).get('url', 'https://api.pdfcheck.cz')
        self.api_key = self.config.get('api', {}).get('key', '')
        self.remote_config = None
        self.fetch_remote_config()

    def load_config(self):
        """Načte konfiguraci z YAML"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except:
                return {}
        return {}

    def save_config(self, config):
        """Uloží konfiguraci do YAML"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            self.config = config
            self.api_key = config.get('api', {}).get('key', '')
            return True
        except Exception as e:
            print(f"Chyba při ukládání konfigurace: {e}")
            return False

    def verify_api_key(self, api_key=None):
        """Ověří API klíč se serverem"""
        key_to_verify = api_key or self.api_key
        if not key_to_verify:
            return False, "API klíč není zadán"
        try:
            headers = self._api_headers(key_to_verify)
            response = requests.get(
                f"{self.api_url}/api/auth/verify",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return True, data.get('message', 'API klíč je platný')
            elif response.status_code == 401:
                return False, "Neplatný API klíč"
            elif response.status_code == 403:
                return False, "API klíč není autorizován"
            else:
                return False, f"Server vrátil chybu: {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Nelze se připojit k serveru (zkontrolujte internet)"
        except requests.exceptions.Timeout:
            return False, "Časový limit připojení vypršel"
        except Exception as e:
            return False, f"Chyba při ověřování: {str(e)}"

    def save_api_key(self, api_key):
        """Uloží API klíč do konfigurace"""
        config = self.config.copy()
        if 'api' not in config:
            config['api'] = {}
        config['api']['key'] = api_key
        return self.save_config(config)

    def has_valid_key(self):
        """Zkontroluje zda existuje API klíč"""
        return bool(self.api_key and self.api_key.strip())

    def fetch_remote_config(self):
        """Získá aktuální disclaimery a texty ze serveru (bez API klíče)."""
        try:
            response = requests.get(
                f"{self.api_url.rstrip('/')}/api/agent-config",
                timeout=5,
            )
            if response.status_code == 200:
                self.remote_config = response.json()
            else:
                self.remote_config = self._get_default_config()
        except Exception:
            self.remote_config = self._get_default_config()

    def _get_default_config(self):
        """Záložní texty, pokud vypadne internet."""
        return {
            "disclaimer": "Výsledek je informativní. Za správnost odpovídá projektant.",
            "vop_link": "https://cieslar.pythonanywhere.com/vop",
            "update_msg": "Používáte aktuální verzi.",
            "allowed_extensions": [".pdf"],
            "analysis_timeout_seconds": 300,
        }

    def _api_headers(self, api_key=None):
        """Základní hlavičky pro každý API request: Authorization + X-Machine-ID, X-Machine-Name."""
        key = api_key or self.api_key or ''
        h = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {key}',
        }
        mid = get_machine_id()
        host = get_hostname()
        if mid:
            h['X-Machine-ID'] = mid
        if host:
            h['X-Machine-Name'] = host
        return h

    def clear_api_key(self):
        """Odstraní API klíč z konfigurace (odhlášení)"""
        config = self.config.copy()
        if "api" not in config:
            config["api"] = {}
        config["api"]["key"] = ""
        self.api_key = ""
        return self.save_config(config)

    def login_with_password(self, email, password):
        """Přihlášení e-mailem a heslem na serveru."""
        if not email or not str(email).strip():
            return False, None, "Zadejte e-mail"
        if not password:
            return False, None, "Zadejte heslo"
        try:
            headers = self._api_headers('')
            headers["Content-Type"] = "application/json"
            response = requests.post(
                f"{self.api_url}/api/auth/user-login",
                json={"email": email.strip(), "password": password},
                headers=headers,
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("api_key"):
                    api_key = data["api_key"]
                    self.save_api_key(api_key)
                    self.api_key = api_key
                    tier_name = data.get("tier_name") or "—"
                    max_batch = data.get("max_batch_size")
                    if str(tier_name).strip().lower() == "trial":
                        display = f"Režim: Trial verze – Limit {max_batch if max_batch is not None else 5} souborů"
                    else:
                        user_name = data.get("user_name") or data.get("email") or "—"
                        display = f"{user_name} ({data.get('email', '')}) – {tier_name}"
                    return True, api_key, display
                return False, None, data.get("error", "Chyba přihlášení")
            err = (response.json() or {}).get("error", f"Server vrátil {response.status_code}")
            return False, None, err
        except requests.exceptions.ConnectionError:
            return False, None, "Nelze se připojit k serveru"
        except requests.exceptions.Timeout:
            return False, None, "Časový limit vypršel"
        except Exception as e:
            return False, None, str(e)

    def get_license_info(self, api_key=None):
        """Získá informace o licenci ze serveru."""
        key = api_key or self.api_key
        if not key or not key.strip():
            return False, "API klíč není zadán"
        try:
            response = requests.get(
                f"{self.api_url}/api/license/info",
                headers=self._api_headers(key),
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                lic = data.get("license") or data
                return True, lic
            if response.status_code == 401:
                return False, "Neplatný API klíč"
            return False, f"Server vrátil chybu: {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Nelze se připojit k serveru"
        except requests.exceptions.Timeout:
            return False, "Časový limit připojení vypršel"
        except Exception as e:
            return False, str(e)

    def upload_batch(self, batch_name, source_folder, results):
        """Odešle CELÝ batch najednou v jednom requestu. Vrátí (success, message, batch_id, response_data)."""
        if not self.has_valid_key():
            return False, "API klíč není nastaven", None, None
        try:
            files_data = []
            for r in results:
                if r.get('success'):
                    files_data.append({
                        'file_name': r.get('file_name'),
                        'file_hash': r.get('file_hash'),
                        'file_size': r.get('file_size'),
                        'processed_at': r.get('processed_at'),
                        'folder': r.get('folder', '.'),
                        'relative_path': r.get('relative_path'),
                        'results': r.get('results')
                    })
            payload = {
                'batch_name': batch_name,
                'source_folder': source_folder,
                'total_files': len(files_data),
                'results': files_data
            }
            headers = self._api_headers(self.api_key)
            response = requests.post(
                f"{self.api_url}/api/batch/upload",
                json=payload,
                headers=headers,
                timeout=60
            )
            if response.status_code in (200, 201):
                data = response.json()
                batch_id = data.get('batch_id')
                saved = data.get('saved_count') or data.get('processed_count') or len(files_data)
                msg = data.get('message') or f"Uloženo {saved} souborů"
                if data.get('status') == 'partial':
                    msg = data.get('message', msg)
                return True, msg, batch_id, data
            elif response.status_code == 401:
                return False, "Neplatný API klíč", None, None
            elif response.status_code == 403:
                try:
                    data = response.json()
                    err = data.get('error') or data.get('message') or "Přístup odepřen"
                    return False, err, None, None
                except Exception:
                    return False, "Zkušební limit vyčerpán. Zakupte si prosím licenci.", None, None
            elif response.status_code == 413:
                return False, "Data jsou příliš velká", None, None
            else:
                return False, f"Server vrátil chybu: {response.status_code}", None, None
        except requests.exceptions.ConnectionError:
            return False, "Nelze se připojit k serveru", None, None
        except requests.exceptions.Timeout:
            return False, "Časový limit vypršel", None, None
        except Exception as e:
            return False, f"Chyba: {str(e)}", None, None

    def get_auto_send_setting(self):
        """Vrátí nastavení auto_send"""
        return self.config.get('agent', {}).get('auto_send', True)

    def get_show_results_setting(self):
        """Vrátí nastavení show_results_window"""
        return self.config.get('agent', {}).get('show_results_window', True)
