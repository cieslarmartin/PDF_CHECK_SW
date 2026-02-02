# database.py
# SQLite databáze pro PDF DokuCheck Web Backend
# Build 41 | © 2025 Ing. Martin Cieślar
# NOVÉ: Licenční systém, device binding, feature flags, Admin systém

import sqlite3
import json
from datetime import datetime, timedelta
import os
import uuid

# Absolute DB path (required on PythonAnywhere/WSGI – CWD may not be app dir)
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'pdfcheck_results.db')
_default_db_path = db_path  # used by Database.__init__ when no path is passed

import hashlib
import secrets

# Import licenční konfigurace
try:
    from license_config import LicenseTier, tier_from_string, tier_to_string
except ImportError:
    # Fallback pokud není k dispozici
    class LicenseTier:
        FREE = 0
        BASIC = 1
        PRO = 2
        ENTERPRISE = 3
    def tier_from_string(s): return LicenseTier.FREE
    def tier_to_string(t): return "Free"


class Database:
    """Správa SQLite databáze pro výsledky kontrol"""

    def __init__(self, db_path=None):
        self.db_path = db_path if db_path is not None else _default_db_path  # absolute path on PA
        self.init_database()

    def get_connection(self):
        """Vytvoří připojení k databázi"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Vrací dict místo tuple
        return conn

    def init_database(self):
        """Inicializuje databázové tabulky"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Tabulka API klíčů - ROZŠÍŘENÁ o licenční údaje
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key TEXT UNIQUE NOT NULL,
                user_name TEXT,
                email TEXT,
                license_tier INTEGER DEFAULT 0,
                license_expires TIMESTAMP,
                max_devices INTEGER DEFAULT 1,
                rate_limit_hour INTEGER DEFAULT 3,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')

        # NOVÁ: Tabulka aktivací zařízení (device binding)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS device_activations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key TEXT NOT NULL,
                hwid TEXT NOT NULL,
                device_name TEXT,
                os_info TEXT,
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (api_key) REFERENCES api_keys(api_key),
                UNIQUE(api_key, hwid)
            )
        ''')

        # NOVÁ: Tabulka rate limitingu pro free tier
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rate_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier TEXT NOT NULL,
                identifier_type TEXT DEFAULT 'ip',
                action_type TEXT DEFAULT 'check',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # NOVÁ: Tabulka dávek (batches)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT UNIQUE NOT NULL,
                api_key TEXT NOT NULL,
                batch_name TEXT,
                source_folder TEXT,
                total_files INTEGER DEFAULT 0,
                pdf_a3_count INTEGER DEFAULT 0,
                signed_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (api_key) REFERENCES api_keys(api_key)
            )
        ''')

        # Tabulka výsledků kontrol - UPRAVENÁ s batch_id a folder strukturou
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS check_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key TEXT NOT NULL,
                batch_id TEXT,
                file_name TEXT NOT NULL,
                file_path TEXT,
                folder_path TEXT,
                file_hash TEXT,
                file_size INTEGER,
                processed_at TIMESTAMP,
                is_pdf_a3 BOOLEAN,
                pdf_version TEXT,
                signature_count INTEGER,
                has_errors BOOLEAN,
                results_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (api_key) REFERENCES api_keys(api_key),
                FOREIGN KEY (batch_id) REFERENCES batches(batch_id)
            )
        ''')

        # Indexy pro rychlejší vyhledávání
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_key ON check_results(api_key)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_batch_id ON check_results(batch_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_hash ON check_results(file_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_folder_path ON check_results(folder_path)')

        # Indexy pro licenční systém
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_device_api_key ON device_activations(api_key)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_device_hwid ON device_activations(hwid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rate_identifier ON rate_limits(identifier)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rate_timestamp ON rate_limits(timestamp)')

        # NOVÁ: Tabulka admin uživatelů
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'USER',
                display_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_admin_email ON admin_users(email)')

        # User analytics & security: request log (every request)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action_type TEXT NOT NULL,
                file_count INTEGER DEFAULT 0,
                total_size_kb INTEGER DEFAULT 0,
                ip_address TEXT,
                machine_id TEXT,
                status TEXT DEFAULT 'ok',
                FOREIGN KEY (user_id) REFERENCES api_keys(api_key)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_logs_user_id ON user_logs(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_logs_timestamp ON user_logs(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_logs_action ON user_logs(action_type)')

        # User devices (unique machines per user, blockable)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                machine_id TEXT NOT NULL,
                machine_name TEXT,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_blocked BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, machine_id),
                FOREIGN KEY (user_id) REFERENCES api_keys(api_key)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_devices_user_id ON user_devices(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_devices_machine_id ON user_devices(machine_id)')

        # Globální definice tierů (Free, Basic, Pro, Enterprise) – upravitelné v Admin
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS license_tiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                max_files_limit INTEGER NOT NULL DEFAULT 10,
                allow_signatures BOOLEAN DEFAULT 0,
                allow_timestamp BOOLEAN DEFAULT 0,
                allow_excel_export BOOLEAN DEFAULT 0,
                max_devices INTEGER NOT NULL DEFAULT 1
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_license_tiers_name ON license_tiers(name)')

        # Globální nastavení (Maintenance Mode, Allow New Registrations)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS global_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')

        # Trial usage: celkový počet souborů zpracovaných na zařízení (Machine-ID) v režimu Trial
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trial_usage (
                machine_id TEXT PRIMARY KEY,
                total_files INTEGER NOT NULL DEFAULT 0,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trial_usage_last_seen ON trial_usage(last_seen)')

        # Historie fakturace (pro uživatele)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS billing_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key TEXT NOT NULL,
                description TEXT,
                amount_cents INTEGER,
                paid_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (api_key) REFERENCES api_keys(api_key)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_billing_api_key ON billing_history(api_key)')

        # Systémové logy (chyby serveru, starty aplikací)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                message TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp ON admin_system_logs(timestamp)')

        # Platební logy (změny tarifů, platby)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES api_keys(api_key)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_payment_logs_user ON payment_logs(user_id)')

        # Migrace: přidej nové sloupce pokud neexistují (pro existující databáze)
        self._migrate_schema(cursor)

        conn.commit()
        conn.close()

    def _migrate_schema(self, cursor):
        """Migruje schéma pro existující databáze"""
        # Získej existující sloupce v api_keys
        cursor.execute("PRAGMA table_info(api_keys)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Přidej chybějící sloupce
        new_columns = {
            'email': 'TEXT',
            'license_tier': 'INTEGER DEFAULT 0',
            'tier_id': 'INTEGER REFERENCES license_tiers(id)',  # FK na globální tier; přednost před license_tier
            'license_expires': 'TIMESTAMP',
            'max_devices': 'INTEGER DEFAULT 1',
            'rate_limit_hour': 'INTEGER DEFAULT 3',
            'password_hash': 'TEXT',  # heslo pro přihlášení uživatele v agentovi (e-mail + heslo)
            'max_batch_size': 'INTEGER',  # NULL = use tier default; override per license
            'allow_signatures': 'BOOLEAN DEFAULT 1',
            'allow_timestamp': 'BOOLEAN DEFAULT 1',
            'allow_excel_export': 'BOOLEAN DEFAULT 1',
            'payment_method': 'TEXT',  # Karta, Převod
            'last_payment_date': 'TIMESTAMP',
        }

        for col_name, col_type in new_columns.items():
            if col_name not in existing_columns:
                try:
                    cursor.execute(f'ALTER TABLE api_keys ADD COLUMN {col_name} {col_type}')
                except sqlite3.OperationalError:
                    pass  # Sloupec už existuje

    def create_api_key(self, api_key, user_name=None):
        """Vytvoří nový API klíč"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO api_keys (api_key, user_name)
                VALUES (?, ?)
            ''', (api_key, user_name))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Klíč už existuje
        finally:
            conn.close()

    def verify_api_key(self, api_key):
        """Ověří platnost API klíče"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, is_active FROM api_keys
            WHERE api_key = ?
        ''', (api_key,))

        result = cursor.fetchone()
        conn.close()

        if result and result['is_active']:
            return True
        return False

    # =========================================================================
    # BATCH OPERACE (NOVÉ v40)
    # =========================================================================

    def create_batch(self, api_key, batch_name=None, source_folder=None):
        """Vytvoří novou dávku a vrátí batch_id"""
        conn = self.get_connection()
        cursor = conn.cursor()

        batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        try:
            cursor.execute('''
                INSERT INTO batches (batch_id, api_key, batch_name, source_folder)
                VALUES (?, ?, ?, ?)
            ''', (batch_id, api_key, batch_name, source_folder))
            conn.commit()
            return batch_id
        except Exception as e:
            print(f"Chyba při vytváření batch: {e}")
            return None
        finally:
            conn.close()

    def update_batch_stats(self, batch_id):
        """Aktualizuje statistiky dávky"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Spočítej statistiky
            cursor.execute('''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_pdf_a3 = 1 THEN 1 ELSE 0 END) as pdf_a3,
                    SUM(CASE WHEN signature_count > 0 THEN 1 ELSE 0 END) as signed
                FROM check_results
                WHERE batch_id = ?
            ''', (batch_id,))
            stats = cursor.fetchone()

            cursor.execute('''
                UPDATE batches
                SET total_files = ?, pdf_a3_count = ?, signed_count = ?
                WHERE batch_id = ?
            ''', (stats['total'], stats['pdf_a3'], stats['signed'], batch_id))

            conn.commit()
        finally:
            conn.close()

    def get_batches(self, api_key=None, limit=50):
        """Vrátí seznam dávek"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if api_key:
            cursor.execute('''
                SELECT * FROM batches
                WHERE api_key = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (api_key, limit))
        else:
            cursor.execute('''
                SELECT * FROM batches
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_batch_api_key(self, batch_id):
        """Vrátí api_key vlastníka dávky (pro ověření přístupu)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT api_key FROM batches WHERE batch_id = ?', (batch_id,))
        row = cursor.fetchone()
        conn.close()
        return row['api_key'] if row else None

    def get_batch_results(self, batch_id):
        """Vrátí všechny výsledky pro danou dávku"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM check_results
            WHERE batch_id = ?
            ORDER BY folder_path, file_name
        ''', (batch_id,))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Parsuj JSON
        for result in results:
            if result.get('results_json'):
                result['parsed_results'] = json.loads(result['results_json'])

        return results

    def delete_batch(self, batch_id):
        """Smaže dávku a všechny její výsledky"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM check_results WHERE batch_id = ?', (batch_id,))
            cursor.execute('DELETE FROM batches WHERE batch_id = ?', (batch_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Chyba při mazání batch: {e}")
            return False
        finally:
            conn.close()

    def delete_all_results(self):
        """Smaže VŠECHNY výsledky a batche (pouze admin)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM check_results')
            count = cursor.fetchone()[0]
            cursor.execute('DELETE FROM check_results')
            cursor.execute('DELETE FROM batches')
            conn.commit()
            return count
        except Exception as e:
            print(f"Chyba při mazání všech dat: {e}")
            return 0
        finally:
            conn.close()

    def delete_all_results_for_api_key(self, api_key):
        """Smaže pouze výsledky a batche daného uživatele (pro web – „Vymazat vše“)."""
        if not api_key:
            return 0
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM check_results WHERE api_key = ?', (api_key,))
            count = cursor.fetchone()[0]
            cursor.execute('DELETE FROM check_results WHERE api_key = ?', (api_key,))
            cursor.execute('DELETE FROM batches WHERE api_key = ?', (api_key,))
            conn.commit()
            return count
        except Exception as e:
            print(f"Chyba při mazání dat uživatele: {e}")
            return 0
        finally:
            conn.close()

    # =========================================================================
    # VÝSLEDKY S BATCH PODPOROU
    # =========================================================================

    def save_result(self, api_key, result_data, batch_id=None):
        """Uloží výsledek kontroly do databáze"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Extrahuj data z result_data
            file_name = result_data.get('file_name')
            file_path = result_data.get('relative_path') or result_data.get('file_path') or file_name
            folder_path = result_data.get('folder') or os.path.dirname(file_path) or '.'
            file_hash = result_data.get('file_hash')
            file_size = result_data.get('file_size')
            processed_at = result_data.get('processed_at')

            results = result_data.get('results', {})
            pdf_format = results.get('pdf_format', {})
            signatures = results.get('signatures', [])

            is_pdf_a3 = pdf_format.get('is_pdf_a3', False)
            pdf_version = pdf_format.get('exact_version', 'Unknown')
            signature_count = len(signatures)
            has_errors = not result_data.get('success', True)

            # Ulož jako JSON string
            results_json = json.dumps(result_data, ensure_ascii=False)

            cursor.execute('''
                INSERT INTO check_results (
                    api_key, batch_id, file_name, file_path, folder_path, file_hash, file_size, processed_at,
                    is_pdf_a3, pdf_version, signature_count, has_errors, results_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                api_key, batch_id, file_name, file_path, folder_path, file_hash, file_size, processed_at,
                is_pdf_a3, pdf_version, signature_count, has_errors, results_json
            ))

            conn.commit()
            return True, cursor.lastrowid

        except Exception as e:
            return False, str(e)
        finally:
            conn.close()

    def get_results_by_api_key(self, api_key, limit=100, offset=0):
        """Vrátí výsledky pro daný API klíč"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM check_results
            WHERE api_key = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        ''', (api_key, limit, offset))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Parsuj JSON zpět
        for result in results:
            if result.get('results_json'):
                result['parsed_results'] = json.loads(result['results_json'])

        return results

    def get_statistics(self, api_key):
        """Vrátí statistiky pro API klíč"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Celkový počet kontrol
        cursor.execute('''
            SELECT COUNT(*) as total FROM check_results
            WHERE api_key = ?
        ''', (api_key,))
        total = cursor.fetchone()['total']

        # PDF/A-3 kontroly
        cursor.execute('''
            SELECT COUNT(*) as count FROM check_results
            WHERE api_key = ? AND is_pdf_a3 = 1
        ''', (api_key,))
        pdf_a3_count = cursor.fetchone()['count']

        # Kontroly s chybami
        cursor.execute('''
            SELECT COUNT(*) as count FROM check_results
            WHERE api_key = ? AND has_errors = 1
        ''', (api_key,))
        errors_count = cursor.fetchone()['count']

        # Kontroly s podpisy
        cursor.execute('''
            SELECT COUNT(*) as count FROM check_results
            WHERE api_key = ? AND signature_count > 0
        ''', (api_key,))
        signed_count = cursor.fetchone()['count']

        conn.close()

        return {
            'total_checks': total,
            'pdf_a3_count': pdf_a3_count,
            'pdf_a3_percentage': (pdf_a3_count / total * 100) if total > 0 else 0,
            'errors_count': errors_count,
            'success_count': total - errors_count,
            'signed_count': signed_count
        }

    def get_all_api_keys(self):
        """Vrátí všechny API klíče (pro admin)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM api_keys ORDER BY created_at DESC')
        keys = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return keys

    # =========================================================================
    # AGENT RESULTS (pro webové rozhraní)
    # =========================================================================

    def get_agent_results_grouped(self, limit=50, api_key=None):
        """
        Vrátí výsledky seskupené podle batchů pro webové rozhraní.
        Pokud je api_key zadán, vrací jen batche tohoto uživatele (pro přihlášené na webu).
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Získej batche (volitelně jen pro daného uživatele)
        if api_key:
            cursor.execute('''
                SELECT * FROM batches
                WHERE api_key = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (api_key, limit))
        else:
            cursor.execute('''
                SELECT * FROM batches
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
        batches = [dict(row) for row in cursor.fetchall()]

        # Pro každý batch získej výsledky
        for batch in batches:
            cursor.execute('''
                SELECT * FROM check_results
                WHERE batch_id = ?
                ORDER BY folder_path, file_name
            ''', (batch['batch_id'],))
            results = [dict(row) for row in cursor.fetchall()]

            # Parsuj JSON
            for result in results:
                if result.get('results_json'):
                    result['parsed_results'] = json.loads(result['results_json'])

            batch['results'] = results

            # Vytvoř stromovou strukturu složek
            batch['folder_tree'] = self._build_folder_tree(results)

        conn.close()

        # Také získej výsledky bez batch_id (staré záznamy) – při api_key jen tohoto uživatele
        conn2 = self.get_connection()
        cursor2 = conn2.cursor()
        if api_key:
            cursor2.execute('''
                SELECT * FROM check_results
                WHERE batch_id IS NULL AND api_key = ?
                ORDER BY created_at DESC
                LIMIT 500
            ''', (api_key,))
        else:
            cursor2.execute('''
                SELECT * FROM check_results
                WHERE batch_id IS NULL
                ORDER BY created_at DESC
                LIMIT 500
            ''')
        legacy_results = [dict(row) for row in cursor2.fetchall()]
        conn2.close()

        for result in legacy_results:
            if result.get('results_json'):
                result['parsed_results'] = json.loads(result['results_json'])

        # Seskup legacy výsledky podle data
        if legacy_results:
            legacy_grouped = {}
            for r in legacy_results:
                date = r['created_at'].split(' ')[0] if r.get('created_at') else 'Neznámé'
                if date not in legacy_grouped:
                    legacy_grouped[date] = []
                legacy_grouped[date].append(r)

            # Přidej jako pseudo-batche
            for date, results in legacy_grouped.items():
                batches.append({
                    'batch_id': f'legacy_{date}',
                    'batch_name': f'Import - {date}',
                    'source_folder': None,
                    'total_files': len(results),
                    'created_at': date,
                    'results': results,
                    'folder_tree': self._build_folder_tree(results),
                    'is_legacy': True
                })

        return batches

    def _build_folder_tree(self, results):
        """Vytvoří stromovou strukturu složek z výsledků"""
        tree = {}

        for result in results:
            folder = result.get('folder_path') or '.'

            if folder not in tree:
                tree[folder] = []

            tree[folder].append({
                'file_name': result.get('file_name'),
                'file_path': result.get('file_path'),
                'is_pdf_a3': result.get('is_pdf_a3'),
                'signature_count': result.get('signature_count'),
                'parsed_results': result.get('parsed_results')
            })

        return tree

    # =========================================================================
    # LICENČNÍ SYSTÉM (NOVÉ v41)
    # =========================================================================

    def create_api_key_with_license(self, api_key, user_name=None, email=None,
                                     license_tier=0, license_days=None, password=None):
        """Vytvoří nový API klíč s licenčními údaji. password = heslo pro přihlášení uživatele (e-mail+heslo) v agentovi."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            license_expires = None
            if license_days and license_days > 0:
                license_expires = (datetime.now() + timedelta(days=license_days)).isoformat()

            try:
                from license_config import get_tier_limits, LicenseTier
                limits = get_tier_limits(LicenseTier(license_tier))
                max_devices = limits.get('max_devices', 1)
                rate_limit = limits.get('rate_limit_per_hour', 3)
                max_batch_size = limits.get('max_files_per_batch', 5)
            except ImportError:
                max_devices = 1
                rate_limit = 3
                max_batch_size = 5

            password_hash = self._hash_password(password) if password and str(password).strip() else None

            # Insert with feature flags (allow_signatures, allow_timestamp, allow_excel_export default 1)
            cursor.execute('''
                INSERT INTO api_keys (api_key, user_name, email, license_tier,
                                     license_expires, max_devices, rate_limit_hour, password_hash,
                                     max_batch_size, allow_signatures, allow_timestamp, allow_excel_export)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 1)
            ''', (api_key, user_name, email, license_tier, license_expires,
                  max_devices, rate_limit, password_hash, max_batch_size))
            try:
                cursor.execute('UPDATE api_keys SET tier_id = ? WHERE api_key = ?', (license_tier + 1, api_key))
            except sqlite3.OperationalError:
                pass
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_license_by_email(self, email):
        """Vrátí záznam licence podle e-mailu (pro přihlášení uživatele)."""
        if not email or not str(email).strip():
            return None
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, api_key, user_name, email, license_tier, license_expires,
                   max_devices, rate_limit_hour, created_at, is_active, password_hash
            FROM api_keys
            WHERE LOWER(TRIM(email)) = LOWER(TRIM(?)) AND is_active = 1
        ''', (email.strip(),))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def verify_license_password(self, email, password):
        """
        Ověří přihlášení uživatele e-mailem a heslem.
        Vrátí (True, license_info_dict) nebo (False, error_message).
        license_info_dict obsahuje api_key, user_name, email, tier_name (bez password_hash).
        """
        row = self.get_license_by_email(email)
        if not row:
            return False, "Neplatný e-mail nebo heslo"
        if not row.get('is_active'):
            return False, "Účet je deaktivován"
        license_info = self.get_user_license(row['api_key'])
        if license_info and license_info.get('is_expired'):
            return False, "Licence vypršela"
        ph = row.get('password_hash')
        if not ph:
            return False, "Pro tento účet není nastaveno heslo – použijte licenční klíč v agentovi"
        if not self._verify_password(password, ph):
            return False, "Neplatný e-mail nebo heslo"
        # Vrátit údaje včetně tier_name a max_batch_size z get_user_license (DB tier, ne hardcoded)
        license_info = self.get_user_license(row['api_key'])
        tier_name = (license_info or {}).get('tier_name') or tier_to_string(LicenseTier(row.get('license_tier', 0)))
        max_batch_size = (license_info or {}).get('max_batch_size')
        out = {
            'api_key': row['api_key'],
            'user_name': row.get('user_name'),
            'email': row.get('email'),
            'license_tier': row.get('license_tier', 0),
            'tier_name': tier_name,
            'max_batch_size': max_batch_size,
        }
        return True, out

    def get_user_license(self, api_key):
        """Vrátí kompletní licenční informace pro API klíč"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM api_keys WHERE api_key = ?', (api_key,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        result = dict(row)

        # Přednost: globální tier (tier_id) před legacy license_tier (0–3)
        tier_row = self.get_tier_by_id(result.get('tier_id')) if result.get('tier_id') else None
        if tier_row:
            result['max_batch_size'] = result.get('max_batch_size') if result.get('max_batch_size') is not None else tier_row.get('max_files_limit', 10)
            result['allow_signatures'] = bool(tier_row.get('allow_signatures', 0))
            result['allow_timestamp'] = bool(tier_row.get('allow_timestamp', 0))
            result['allow_excel_export'] = bool(tier_row.get('allow_excel_export', 0))
            result['max_devices'] = tier_row.get('max_devices', 1)
            result['tier_name'] = tier_row.get('name', 'Unknown')
        else:
            try:
                from license_config import get_tier_limits
                tier = LicenseTier(result.get('license_tier', 0))
                limits = get_tier_limits(tier)
                if result.get('max_batch_size') is None:
                    result['max_batch_size'] = limits.get('max_files_per_batch', 5)
                if result.get('allow_signatures') is None:
                    result['allow_signatures'] = True
                if result.get('allow_timestamp') is None:
                    result['allow_timestamp'] = True
                if result.get('allow_excel_export') is None:
                    result['allow_excel_export'] = True
                result['max_devices'] = result.get('max_devices') if result.get('max_devices') is not None else limits.get('max_devices', 1)
            except (ImportError, TypeError):
                result.setdefault('max_batch_size', 5)
                result.setdefault('allow_signatures', True)
                result.setdefault('allow_timestamp', True)
                result.setdefault('allow_excel_export', True)
                result.setdefault('max_devices', 1)
            result['tier_name'] = tier_to_string(LicenseTier(result['license_tier']))

        # Zkontroluj expiraci
        if result['license_expires']:
            try:
                exp_date = datetime.fromisoformat(result['license_expires'])
                result['is_expired'] = exp_date < datetime.now()
                result['days_remaining'] = (exp_date - datetime.now()).days
            except:
                result['is_expired'] = False
                result['days_remaining'] = -1
        else:
            result['is_expired'] = False
            result['days_remaining'] = -1  # Neomezeno

        # Spočítej aktivní zařízení
        result['active_devices'] = self.count_active_devices(api_key)

        return result

    # =========================================================================
    # TRIAL USAGE (Machine-ID binding, hard limit)
    # =========================================================================

    TRIAL_LIMIT_TOTAL_FILES = 10  # Celkový počet souborů na jedno zařízení v Trial režimu

    def get_trial_usage(self, machine_id):
        """Vrátí { total_files, last_seen } pro dané machine_id, nebo None."""
        if not machine_id or not str(machine_id).strip():
            return None
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT total_files, last_seen FROM trial_usage WHERE machine_id = ?',
            (str(machine_id).strip(),)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else {'total_files': 0, 'last_seen': None}

    def increment_trial_usage(self, machine_id, count=1):
        """Zvýší total_files pro machine_id a aktualizuje last_seen."""
        if not machine_id or not str(machine_id).strip() or count < 1:
            return
        mid = str(machine_id).strip()
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO trial_usage (machine_id, total_files, last_seen)
            VALUES (?, ?, ?)
            ON CONFLICT(machine_id) DO UPDATE SET
                total_files = total_files + ?,
                last_seen = ?
        ''', (mid, count, now, count, now))
        conn.commit()
        conn.close()

    def reset_trial_usage(self, machine_id):
        """Vynuluje počítadlo Trial pro dané machine_id."""
        if not machine_id or not str(machine_id).strip():
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM trial_usage WHERE machine_id = ?', (str(machine_id).strip(),))
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        return deleted > 0

    def list_trial_usage(self):
        """Vrátí seznam všech Trial použití: [ { machine_id, total_files, last_seen }, ... ]."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT machine_id, total_files, last_seen FROM trial_usage ORDER BY last_seen DESC'
        )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def update_license_tier(self, api_key, new_tier, license_days=None):
        """Aktualizuje licenční tier pro uživatele"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Získej limity pro nový tier
            try:
                from license_config import get_tier_limits, LicenseTier
                limits = get_tier_limits(LicenseTier(new_tier))
                max_devices = limits.get('max_devices', 1)
                rate_limit = limits.get('rate_limit_per_hour', 3)
            except ImportError:
                max_devices = 1
                rate_limit = 3

            # Vypočítej novou expiraci
            license_expires = None
            if license_days and license_days > 0:
                license_expires = (datetime.now() + timedelta(days=license_days)).isoformat()

            cursor.execute('''
                UPDATE api_keys
                SET license_tier = ?, license_expires = ?,
                    max_devices = ?, rate_limit_hour = ?
                WHERE api_key = ?
            ''', (new_tier, license_expires, max_devices, rate_limit, api_key))

            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # =========================================================================
    # DEVICE ACTIVATION (Device Binding)
    # =========================================================================

    def register_device(self, api_key, hwid, device_name=None, os_info=None):
        """
        Registruje nové zařízení pro API klíč

        Returns:
            tuple: (success: bool, message: str)
        """
        # Nejprve zkontroluj licenci
        license_info = self.get_user_license(api_key)
        if not license_info:
            return False, "Neplatný API klíč"

        if not license_info['is_active']:
            return False, "Účet je deaktivován"

        if license_info['is_expired']:
            return False, "Licence vypršela"

        # Zkontroluj limit zařízení
        max_devices = license_info.get('max_devices', 1)
        if max_devices != -1:  # -1 = neomezeno
            active_count = self.count_active_devices(api_key)

            # Zkontroluj jestli toto zařízení už není registrováno
            existing = self.get_device_activation(api_key, hwid)
            if existing:
                # Zařízení už existuje - aktualizuj last_seen
                self.update_device_last_seen(api_key, hwid)
                return True, "Zařízení již registrováno"

            if active_count >= max_devices:
                return False, f"Dosažen limit {max_devices} zařízení"

        # Registruj zařízení
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO device_activations (api_key, hwid, device_name, os_info)
                VALUES (?, ?, ?, ?)
            ''', (api_key, hwid, device_name, os_info))
            conn.commit()
            return True, "Zařízení úspěšně registrováno"
        except sqlite3.IntegrityError:
            # Zařízení už existuje
            self.update_device_last_seen(api_key, hwid)
            return True, "Zařízení již registrováno"
        finally:
            conn.close()

    def validate_device(self, api_key, hwid):
        """
        Validuje zařízení pro použití s API klíčem

        Returns:
            tuple: (valid: bool, license_info: dict or error_message: str)
        """
        # Získej licenci
        license_info = self.get_user_license(api_key)
        if not license_info:
            return False, "Neplatný API klíč"

        if not license_info['is_active']:
            return False, "Účet je deaktivován"

        if license_info['is_expired']:
            return False, "Licence vypršela"

        # Zkontroluj zařízení
        device = self.get_device_activation(api_key, hwid)
        if not device:
            # Zkus registrovat automaticky
            success, msg = self.register_device(api_key, hwid)
            if not success:
                return False, msg
            device = self.get_device_activation(api_key, hwid)

        if device and not device['is_active']:
            return False, "Zařízení je deaktivováno"

        # Aktualizuj last_seen
        self.update_device_last_seen(api_key, hwid)

        # Přidej features a limits do výsledku
        try:
            from license_config import get_tier_features, get_tier_limits, LicenseTier
            tier = LicenseTier(license_info['license_tier'])
            license_info['features'] = get_tier_features(tier)
            license_info['limits'] = get_tier_limits(tier)
        except ImportError:
            license_info['features'] = []
            license_info['limits'] = {}

        return True, license_info

    def get_device_activation(self, api_key, hwid):
        """Vrátí informace o aktivaci zařízení"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM device_activations
            WHERE api_key = ? AND hwid = ?
        ''', (api_key, hwid))

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_active_devices(self, api_key):
        """Vrátí seznam aktivních zařízení pro API klíč"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM device_activations
            WHERE api_key = ? AND is_active = 1
            ORDER BY last_seen DESC
        ''', (api_key,))

        devices = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return devices

    def count_active_devices(self, api_key):
        """Spočítá aktivní zařízení pro API klíč"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(*) as count FROM device_activations
            WHERE api_key = ? AND is_active = 1
        ''', (api_key,))

        result = cursor.fetchone()['count']
        conn.close()
        return result

    def update_device_last_seen(self, api_key, hwid):
        """Aktualizuje čas posledního použití zařízení"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE device_activations
            SET last_seen = CURRENT_TIMESTAMP
            WHERE api_key = ? AND hwid = ?
        ''', (api_key, hwid))

        conn.commit()
        conn.close()

    def deactivate_device(self, api_key, hwid):
        """Deaktivuje zařízení"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE device_activations
            SET is_active = 0
            WHERE api_key = ? AND hwid = ?
        ''', (api_key, hwid))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def remove_device(self, api_key, hwid):
        """Odstraní zařízení úplně"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            DELETE FROM device_activations
            WHERE api_key = ? AND hwid = ?
        ''', (api_key, hwid))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    # =========================================================================
    # RATE LIMITING
    # =========================================================================

    def check_rate_limit(self, identifier, identifier_type='ip', action_type='check',
                         max_per_hour=3):
        """
        Zkontroluje a případně zaznamená akci pro rate limiting

        Args:
            identifier: IP adresa nebo jiný identifikátor
            identifier_type: Typ identifikátoru ('ip', 'session', 'fingerprint')
            action_type: Typ akce ('check', 'upload', 'export')
            max_per_hour: Maximální počet akcí za hodinu

        Returns:
            tuple: (allowed: bool, remaining: int, reset_seconds: int)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Spočítej akce za poslední hodinu
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()

        cursor.execute('''
            SELECT COUNT(*) as count FROM rate_limits
            WHERE identifier = ? AND identifier_type = ? AND action_type = ?
            AND timestamp > ?
        ''', (identifier, identifier_type, action_type, one_hour_ago))

        count = cursor.fetchone()['count']

        # Zjisti čas první akce v okně (pro reset time)
        cursor.execute('''
            SELECT MIN(timestamp) as first_action FROM rate_limits
            WHERE identifier = ? AND identifier_type = ? AND action_type = ?
            AND timestamp > ?
        ''', (identifier, identifier_type, action_type, one_hour_ago))

        first_action = cursor.fetchone()['first_action']

        conn.close()

        # Vypočítej zbývající akce a reset time
        remaining = max(0, max_per_hour - count)

        if first_action:
            try:
                first_time = datetime.fromisoformat(first_action)
                reset_time = first_time + timedelta(hours=1)
                reset_seconds = int((reset_time - datetime.now()).total_seconds())
                reset_seconds = max(0, reset_seconds)
            except:
                reset_seconds = 3600
        else:
            reset_seconds = 3600

        return count < max_per_hour, remaining, reset_seconds

    def record_rate_limit_action(self, identifier, identifier_type='ip',
                                  action_type='check'):
        """Zaznamená akci pro rate limiting"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO rate_limits (identifier, identifier_type, action_type)
            VALUES (?, ?, ?)
        ''', (identifier, identifier_type, action_type))

        conn.commit()
        conn.close()

    def cleanup_rate_limits(self, hours_old=24):
        """Vyčistí staré záznamy rate limitingu"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cutoff = (datetime.now() - timedelta(hours=hours_old)).isoformat()

        cursor.execute('''
            DELETE FROM rate_limits
            WHERE timestamp < ?
        ''', (cutoff,))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    # =========================================================================
    # USER LOGS & USER DEVICES (Analytics & Security)
    # =========================================================================

    def insert_user_log(self, user_id, action_type, file_count=0, total_size_kb=0,
                         ip_address=None, machine_id=None, status='ok'):
        """Zapíše záznam do user_logs (každý request). user_id = api_key."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO user_logs (user_id, action_type, file_count, total_size_kb, ip_address, machine_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, action_type, file_count, total_size_kb or 0, ip_address, machine_id, status))
            conn.commit()
        finally:
            conn.close()

    def get_user_devices_list(self, user_id):
        """Vrátí seznam zařízení z user_devices pro daného uživatele (pro admin)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_id, machine_id, machine_name, last_seen, is_blocked, created_at
            FROM user_devices
            WHERE user_id = ?
            ORDER BY last_seen DESC
        ''', (user_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def upsert_user_device(self, user_id, machine_id, machine_name=None):
        """Vloží nebo aktualizuje záznam v user_devices (last_seen, machine_name)."""
        if not user_id or not machine_id or not str(machine_id).strip():
            return
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO user_devices (user_id, machine_id, machine_name, last_seen)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, machine_id) DO UPDATE SET
                    last_seen = CURRENT_TIMESTAMP,
                    machine_name = COALESCE(?, machine_name)
            ''', (user_id, str(machine_id).strip(), machine_name or None, machine_name or None))
            conn.commit()
        except (sqlite3.IntegrityError, sqlite3.OperationalError):
            # SQLite < 3.24 or no ON CONFLICT support; fallback to SELECT + INSERT/UPDATE
            cursor.execute('SELECT id FROM user_devices WHERE user_id = ? AND machine_id = ?',
                           (user_id, str(machine_id).strip()))
            if cursor.fetchone():
                cursor.execute('''
                    UPDATE user_devices SET last_seen = CURRENT_TIMESTAMP, machine_name = COALESCE(?, machine_name)
                    WHERE user_id = ? AND machine_id = ?
                ''', (machine_name, user_id, str(machine_id).strip()))
            else:
                cursor.execute('''
                    INSERT INTO user_devices (user_id, machine_id, machine_name, last_seen)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (user_id, str(machine_id).strip(), machine_name))
            conn.commit()
        finally:
            conn.close()

    def block_user_device(self, user_id, machine_id):
        """Nastaví is_blocked=1 pro dané zařízení uživatele."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_devices SET is_blocked = 1
            WHERE user_id = ? AND machine_id = ?
        ''', (user_id, str(machine_id).strip()))
        n = cursor.rowcount
        conn.commit()
        conn.close()
        return n > 0

    def unblock_user_device(self, user_id, machine_id):
        """Nastaví is_blocked=0 pro dané zařízení."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_devices SET is_blocked = 0
            WHERE user_id = ? AND machine_id = ?
        ''', (user_id, str(machine_id).strip()))
        n = cursor.rowcount
        conn.commit()
        conn.close()
        return n > 0

    def is_user_device_blocked(self, user_id, machine_id):
        """Vrátí True, pokud je zařízení (user_id, machine_id) zablokované v user_devices."""
        if not user_id or not machine_id:
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 1 FROM user_devices
            WHERE user_id = ? AND machine_id = ? AND is_blocked = 1
        ''', (user_id, str(machine_id).strip()))
        row = cursor.fetchone()
        conn.close()
        return row is not None

    def count_user_devices_non_blocked(self, user_id):
        """Počet neblokovaných zařízení uživatele (pro kontrolu limitu)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) AS c FROM user_devices
            WHERE user_id = ? AND (is_blocked = 0 OR is_blocked IS NULL)
        ''', (user_id,))
        n = cursor.fetchone()['c']
        conn.close()
        return n

    # =========================================================================
    # ADMIN SYSTÉM (NOVÉ v41)
    # =========================================================================

    def _hash_password(self, password: str) -> str:
        """Vytvoří hash hesla s náhodnou solí"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
        return f"{salt}${password_hash}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Ověří heslo proti hashi"""
        try:
            salt, stored_hash = password_hash.split('$')
            computed_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                100000
            ).hex()
            return secrets.compare_digest(computed_hash, stored_hash)
        except (ValueError, AttributeError):
            return False

    def create_admin_user(self, email: str, password: str, role: str = 'USER',
                          display_name: str = None) -> tuple:
        """
        Vytvoří nového admin uživatele

        Args:
            email: Email uživatele (unikátní)
            password: Heslo v čitelné formě
            role: 'USER' nebo 'ADMIN'
            display_name: Zobrazované jméno

        Returns:
            tuple: (success: bool, message: str)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            password_hash = self._hash_password(password)

            cursor.execute('''
                INSERT INTO admin_users (email, password_hash, role, display_name)
                VALUES (?, ?, ?, ?)
            ''', (email, password_hash, role.upper(), display_name or email.split('@')[0]))

            conn.commit()
            return True, "Uživatel vytvořen"
        except sqlite3.IntegrityError:
            return False, "Email už existuje"
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()

    def verify_admin_login(self, email: str, password: str) -> tuple:
        """
        Ověří přihlášení admin uživatele

        Returns:
            tuple: (success: bool, user_dict or error_message)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, email, password_hash, role, display_name, is_active
            FROM admin_users
            WHERE email = ?
        ''', (email,))

        row = cursor.fetchone()

        if not row:
            conn.close()
            return False, "Neplatný email nebo heslo"

        user = dict(row)

        if not user['is_active']:
            conn.close()
            return False, "Účet je deaktivován"

        if not self._verify_password(password, user['password_hash']):
            conn.close()
            return False, "Neplatný email nebo heslo"

        # Aktualizuj last_login
        cursor.execute('''
            UPDATE admin_users SET last_login = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (user['id'],))
        conn.commit()
        conn.close()

        # Odstraň hash z výsledku
        del user['password_hash']
        return True, user

    def get_admin_by_email(self, email: str) -> dict:
        """Vrátí admin uživatele podle emailu"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, email, role, display_name, created_at, last_login, is_active
            FROM admin_users
            WHERE email = ?
        ''', (email,))

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_admin_by_id(self, user_id: int) -> dict:
        """Vrátí admin uživatele podle ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, email, role, display_name, created_at, last_login, is_active
            FROM admin_users
            WHERE id = ?
        ''', (user_id,))

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_all_admin_users(self) -> list:
        """Vrátí všechny admin uživatele"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, email, role, display_name, created_at, last_login, is_active
            FROM admin_users
            ORDER BY created_at DESC
        ''')

        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return users

    def update_admin_user(self, user_id: int, **kwargs) -> bool:
        """Aktualizuje admin uživatele"""
        conn = self.get_connection()
        cursor = conn.cursor()

        allowed_fields = ['email', 'role', 'display_name', 'is_active']
        updates = []
        values = []

        for field, value in kwargs.items():
            if field in allowed_fields:
                updates.append(f"{field} = ?")
                values.append(value)
            elif field == 'password' and value:
                updates.append("password_hash = ?")
                values.append(self._hash_password(value))

        if not updates:
            conn.close()
            return False

        values.append(user_id)
        query = f"UPDATE admin_users SET {', '.join(updates)} WHERE id = ?"

        cursor.execute(query, values)
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def delete_admin_user(self, user_id: int) -> bool:
        """Smaže admin uživatele"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM admin_users WHERE id = ?', (user_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def is_admin(self, email: str) -> bool:
        """Zkontroluje zda je uživatel admin"""
        user = self.get_admin_by_email(email)
        return user is not None and user.get('role') == 'ADMIN' and user.get('is_active')

    # =========================================================================
    # LICENSE TIERS (globální definice – upravitelné v Admin)
    # =========================================================================

    def get_all_license_tiers(self) -> list:
        """Vrátí všechny globální tier definice."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM license_tiers ORDER BY id')
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_tier_by_id(self, tier_id) -> dict:
        """Vrátí tier podle id."""
        if tier_id is None:
            return None
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM license_tiers WHERE id = ?', (tier_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_tier(self, tier_id: int, name=None, max_files_limit=None,
                    allow_signatures=None, allow_timestamp=None, allow_excel_export=None,
                    max_devices=None) -> bool:
        """Aktualizuje globální tier."""
        conn = self.get_connection()
        cursor = conn.cursor()
        updates, values = [], []
        if name is not None:
            updates.append('name = ?')
            values.append(name)
        if max_files_limit is not None:
            updates.append('max_files_limit = ?')
            values.append(max_files_limit)
        if allow_signatures is not None:
            updates.append('allow_signatures = ?')
            values.append(1 if allow_signatures else 0)
        if allow_timestamp is not None:
            updates.append('allow_timestamp = ?')
            values.append(1 if allow_timestamp else 0)
        if allow_excel_export is not None:
            updates.append('allow_excel_export = ?')
            values.append(1 if allow_excel_export else 0)
        if max_devices is not None:
            updates.append('max_devices = ?')
            values.append(max_devices)
        if not updates:
            conn.close()
            return True
        values.append(tier_id)
        cursor.execute(f'UPDATE license_tiers SET {", ".join(updates)} WHERE id = ?', values)
        ok = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return ok

    # =========================================================================
    # GLOBAL SETTINGS (Maintenance Mode, Allow New Registrations)
    # =========================================================================

    def get_global_setting(self, key: str, default=None):
        """Vrátí hodnotu globálního nastavení (řetězec)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM global_settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return default
        val = row['value']
        if val in ('1', 'true', 'yes'):
            return True
        if val in ('0', 'false', 'no'):
            return False
        return val

    def set_global_setting(self, key: str, value) -> None:
        """Nastaví globální nastavení (value bude převedeno na řetězec)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        v = '1' if value is True else ('0' if value is False else str(value))
        cursor.execute(
            'INSERT OR REPLACE INTO global_settings (key, value) VALUES (?, ?)',
            (key, v)
        )
        conn.commit()
        conn.close()

    # =========================================================================
    # USER LOGS (pro Admin Logs stránku a User Audit)
    # =========================================================================

    def get_user_logs(self, user_id=None, limit=500, offset=0, search=None, date_from=None, date_to=None):
        """Vrátí záznamy z user_logs. user_id = api_key (volitelné). search = filtr. date_from/date_to = YYYY-MM-DD."""
        conn = self.get_connection()
        cursor = conn.cursor()
        sql_extra = []
        params_extra = []
        if date_from:
            sql_extra.append('DATE(timestamp) >= ?')
            params_extra.append(date_from)
        if date_to:
            sql_extra.append('DATE(timestamp) <= ?')
            params_extra.append(date_to)
        where_extra = (' AND ' + ' AND '.join(sql_extra)) if sql_extra else ''
        if user_id:
            if search:
                cursor.execute('''
                    SELECT * FROM user_logs
                    WHERE user_id = ? AND (action_type LIKE ? OR status LIKE ? OR ip_address LIKE ?)''' + where_extra + '''
                    ORDER BY timestamp DESC LIMIT ? OFFSET ?
                ''', (user_id, f'%{search}%', f'%{search}%', f'%{search}%', *params_extra, limit, offset))
            else:
                cursor.execute('''
                    SELECT * FROM user_logs WHERE user_id = ?''' + where_extra + '''
                    ORDER BY timestamp DESC LIMIT ? OFFSET ?
                ''', (user_id, *params_extra, limit, offset))
        else:
            if search:
                cursor.execute('''
                    SELECT * FROM user_logs
                    WHERE (action_type LIKE ? OR user_id LIKE ? OR status LIKE ? OR ip_address LIKE ?)''' + where_extra + '''
                    ORDER BY timestamp DESC LIMIT ? OFFSET ?
                ''', (f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%', *params_extra, limit, offset))
            else:
                cursor.execute('''
                    SELECT * FROM user_logs WHERE 1=1''' + where_extra + '''
                    ORDER BY timestamp DESC LIMIT ? OFFSET ?
                ''', (*params_extra, limit, offset))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_activity_last_30_days(self):
        """Pro Chart.js: počet zpracovaných souborů po dnech (posledních 30 dní). Vrací list [{date, files}, ...]."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DATE(timestamp) AS d, SUM(file_count) AS total
            FROM user_logs
            WHERE timestamp >= DATE('now', '-30 days') AND action_type = 'batch_upload'
            GROUP BY DATE(timestamp)
            ORDER BY d
        ''')
        rows = [{'date': row['d'], 'files': row['total'] or 0} for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_activity_for_period(self, date_from=None, date_to=None):
        """Počet kontrol (souborů) za období. date_from/date_to ve formátu YYYY-MM-DD."""
        conn = self.get_connection()
        cursor = conn.cursor()
        sql = '''
            SELECT DATE(timestamp) AS d, SUM(file_count) AS total
            FROM user_logs
            WHERE action_type = 'batch_upload'
        '''
        params = []
        if date_from:
            sql += ' AND DATE(timestamp) >= ?'
            params.append(date_from)
        if date_to:
            sql += ' AND DATE(timestamp) <= ?'
            params.append(date_to)
        sql += ' GROUP BY DATE(timestamp) ORDER BY d'
        cursor.execute(sql, params)
        rows = [{'date': row['d'], 'files': row['total'] or 0} for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_user_activity_ranking(self, limit=10):
        """Nejaktivnější uživatelé (součet file_count z user_logs). Vrací [{user_id, email, total_files}, ...]."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ul.user_id, SUM(ul.file_count) AS total
            FROM user_logs ul
            WHERE ul.action_type = 'batch_upload' AND ul.timestamp >= DATE('now', '-30 days')
            GROUP BY ul.user_id
            ORDER BY total DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            cursor.execute('SELECT email, user_name FROM api_keys WHERE api_key = ?', (row['user_id'],))
            ak = cursor.fetchone()
            result.append({
                'user_id': row['user_id'],
                'email': ak['email'] if ak else row['user_id'][:20],
                'user_name': ak['user_name'] if ak else None,
                'total_files': row['total'] or 0,
            })
        conn.close()
        return result

    def get_trial_stats(self):
        """Statistiky Trialu: počet unikátních Machine-ID, celkem souborů, seznam (pro graf)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) AS cnt FROM trial_usage')
        unique_machines = cursor.fetchone()['cnt']
        cursor.execute('SELECT COALESCE(SUM(total_files), 0) AS total FROM trial_usage')
        total_files = cursor.fetchone()['total']
        cursor.execute('SELECT machine_id, total_files, last_seen FROM trial_usage ORDER BY total_files DESC LIMIT 20')
        top = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {'unique_machines': unique_machines, 'total_files': total_files, 'top': top}

    def get_dashboard_kpis(self):
        """KPI: celkový obrat (simulovaný), aktivní licence Free vs Paid, chybovost (úspěšné vs neúspěšné)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) AS c FROM api_keys WHERE is_active = 1')
        active_total = cursor.fetchone()['c']
        try:
            cursor.execute('''
                SELECT COUNT(*) AS c FROM api_keys ak
                LEFT JOIN license_tiers lt ON ak.tier_id = lt.id
                WHERE ak.is_active = 1 AND (
                    UPPER(TRIM(COALESCE(lt.name, ''))) IN ('FREE', 'TRIAL') OR
                    (ak.tier_id IS NULL AND COALESCE(ak.license_tier, 0) = 0)
                )
            ''')
            free_count = cursor.fetchone()['c']
        except Exception:
            free_count = active_total
        paid_count = max(0, active_total - free_count)
        cursor.execute('SELECT COUNT(*) AS ok FROM check_results WHERE has_errors = 0')
        ok_count = cursor.fetchone()['ok']
        cursor.execute('SELECT COUNT(*) AS err FROM check_results WHERE has_errors = 1')
        err_count = cursor.fetchone()['err']
        total_checks = ok_count + err_count
        error_rate = (err_count / total_checks * 100) if total_checks else 0
        conn.close()
        return {
            'turnover': 0,  # zatím fixní/simulovaný
            'active_licenses': active_total,
            'free_licenses': free_count,
            'paid_licenses': paid_count,
            'total_checks': total_checks,
            'success_checks': ok_count,
            'error_checks': err_count,
            'error_rate_percent': round(error_rate, 1),
        }

    def get_logs_filtered(self, category='user', user_id=None, date_from=None, date_to=None, level=None, limit=200, offset=0):
        """Logy podle kategorie: system, user, payment. level jen pro system."""
        if category == 'system':
            conn = self.get_connection()
            cursor = conn.cursor()
            sql = 'SELECT * FROM admin_system_logs WHERE 1=1'
            params = []
            if level:
                sql += ' AND level = ?'
                params.append(level)
            if date_from:
                sql += ' AND DATE(timestamp) >= ?'
                params.append(date_from)
            if date_to:
                sql += ' AND DATE(timestamp) <= ?'
                params.append(date_to)
            if user_id:
                sql += ' AND user_id = ?'
                params.append(user_id)
            sql += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            cursor.execute(sql, params)
            rows = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return rows
        if category == 'payment':
            conn = self.get_connection()
            cursor = conn.cursor()
            sql = 'SELECT * FROM payment_logs WHERE 1=1'
            params = []
            if user_id:
                sql += ' AND user_id = ?'
                params.append(user_id)
            if date_from:
                sql += ' AND DATE(timestamp) >= ?'
                params.append(date_from)
            if date_to:
                sql += ' AND DATE(timestamp) <= ?'
                params.append(date_to)
            sql += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            cursor.execute(sql, params)
            rows = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return rows
        # user
        return self.get_user_logs(user_id=user_id, limit=limit, offset=offset, search=None, date_from=date_from, date_to=date_to)

    def insert_system_log(self, level, message, user_id=None):
        """Zápis do systémových logů."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO admin_system_logs (level, message, user_id) VALUES (?, ?, ?)',
            (level, message, user_id)
        )
        conn.commit()
        conn.close()

    def insert_payment_log(self, user_id, action, details=None):
        """Zápis do platebních logů (změna tieru, platba)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO payment_logs (user_id, action, details) VALUES (?, ?, ?)',
            (user_id, action, details)
        )
        conn.commit()
        conn.close()

    def get_billing_history(self, api_key, limit=50):
        """Historie fakturace pro uživatele."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM billing_history WHERE api_key = ? ORDER BY created_at DESC LIMIT ?',
            (api_key, limit)
        )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def add_billing_record(self, api_key, description=None, amount_cents=None, paid_at=None):
        """Přidá záznam do historie fakturace."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO billing_history (api_key, description, amount_cents, paid_at) VALUES (?, ?, ?, ?)',
            (api_key, description, amount_cents, paid_at)
        )
        conn.commit()
        conn.close()

    def admin_update_user_full(self, api_key, user_name=None, email=None, license_expires=None,
                                is_active=None, payment_method=None, last_payment_date=None):
        """Rozšířená aktualizace uživatele: jméno, email, expirace, status, platební údaje."""
        if not api_key or not str(api_key).strip():
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        updates, values = [], []
        if user_name is not None:
            updates.append('user_name = ?')
            values.append(user_name)
        if email is not None:
            updates.append('email = ?')
            values.append(email)
        if license_expires is not None:
            updates.append('license_expires = ?')
            values.append(license_expires)
        if is_active is not None:
            updates.append('is_active = ?')
            values.append(1 if is_active else 0)
        if payment_method is not None:
            updates.append('payment_method = ?')
            values.append(payment_method)
        if last_payment_date is not None:
            updates.append('last_payment_date = ?')
            values.append(last_payment_date)
        if not updates:
            conn.close()
            return True
        values.append(api_key.strip())
        cursor.execute(f'UPDATE api_keys SET {", ".join(updates)} WHERE api_key = ?', values)
        ok = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return ok

    def get_user_last_active(self, api_key):
        """Vrátí čas poslední aktivity uživatele (max timestamp z user_logs) nebo None."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(timestamp) AS t FROM user_logs WHERE user_id = ?', (api_key,))
        row = cursor.fetchone()
        conn.close()
        return row['t'] if row and row['t'] else None

    # =========================================================================
    # ADMIN: SPRÁVA LICENCÍ (rozšířené metody)
    # =========================================================================

    def admin_get_all_licenses(self) -> list:
        """Vrátí všechny licence s detailními informacemi pro admin dashboard (včetně tier z license_tiers a last_active)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT
                    ak.id,
                    ak.api_key,
                    ak.user_name,
                    ak.email,
                    ak.license_tier,
                    ak.tier_id,
                    ak.license_expires,
                    ak.max_devices,
                    ak.rate_limit_hour,
                    ak.created_at,
                    ak.is_active,
                    ak.max_batch_size,
                    ak.allow_signatures,
                    ak.allow_timestamp,
                    ak.allow_excel_export,
                    lt.name AS tier_name_override,
                    (SELECT COUNT(*) FROM device_activations da
                     WHERE da.api_key = ak.api_key AND da.is_active = 1) as active_devices,
                    (SELECT COUNT(*) FROM check_results cr
                     WHERE cr.api_key = ak.api_key) as total_checks,
                    (SELECT MAX(timestamp) FROM user_logs ul WHERE ul.user_id = ak.api_key) as last_active
                FROM api_keys ak
                LEFT JOIN license_tiers lt ON ak.tier_id = lt.id
                ORDER BY ak.created_at DESC
            ''')
        except sqlite3.OperationalError:
            # tier_id nebo license_tiers ještě neexistují
            cursor.execute("PRAGMA table_info(api_keys)")
            cols = {r[1] for r in cursor.fetchall()}
            sel = ['ak.id', 'ak.api_key', 'ak.user_name', 'ak.email', 'ak.license_tier', 'ak.license_expires',
                   'ak.max_devices', 'ak.rate_limit_hour', 'ak.created_at', 'ak.is_active', 'ak.max_batch_size',
                   'ak.allow_signatures', 'ak.allow_timestamp', 'ak.allow_excel_export',
                   '(SELECT COUNT(*) FROM device_activations da WHERE da.api_key = ak.api_key AND da.is_active = 1) as active_devices',
                   '(SELECT COUNT(*) FROM check_results cr WHERE cr.api_key = ak.api_key) as total_checks']
            if 'tier_id' in cols:
                sel.append('ak.tier_id')
                sel.append('(SELECT MAX(timestamp) FROM user_logs ul WHERE ul.user_id = ak.api_key) as last_active')
            cursor.execute('SELECT ' + ', '.join(sel) + ' FROM api_keys ak ORDER BY ak.created_at DESC')

        licenses = []
        for row in cursor.fetchall():
            license_data = dict(row)
            license_data['tier_name'] = license_data.pop('tier_name_override', None) or tier_to_string(LicenseTier(license_data.get('license_tier', 0)))
            if 'last_active' not in license_data:
                license_data['last_active'] = self.get_user_last_active(license_data['api_key'])

            # Zkontroluj expiraci
            if license_data['license_expires']:
                try:
                    exp_date = datetime.fromisoformat(license_data['license_expires'])
                    license_data['is_expired'] = exp_date < datetime.now()
                    license_data['days_remaining'] = (exp_date - datetime.now()).days
                except:
                    license_data['is_expired'] = False
                    license_data['days_remaining'] = -1
            else:
                license_data['is_expired'] = False
                license_data['days_remaining'] = -1

            licenses.append(license_data)

        conn.close()
        return licenses

    def admin_reset_devices(self, api_key: str) -> int:
        """Resetuje všechna zařízení pro daný API klíč (admin funkce)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            DELETE FROM device_activations
            WHERE api_key = ?
        ''', (api_key,))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def admin_delete_license(self, api_key: str) -> bool:
        """Smaže licenci a všechna související data (admin funkce)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Smaž zařízení
            cursor.execute('DELETE FROM device_activations WHERE api_key = ?', (api_key,))
            # Smaž výsledky (volitelně - můžeme nechat)
            # cursor.execute('DELETE FROM check_results WHERE api_key = ?', (api_key,))
            # Smaž API klíč
            cursor.execute('DELETE FROM api_keys WHERE api_key = ?', (api_key,))

            conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting license: {e}")
            return False
        finally:
            conn.close()

    def admin_set_license_password(self, api_key: str, new_password: str) -> bool:
        """Nastaví nebo změní heslo pro přihlášení uživatele v agentovi (e-mail + heslo)."""
        if not api_key or not str(api_key).strip():
            return False
        if not new_password or not str(new_password).strip():
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        password_hash = self._hash_password(new_password.strip())
        cursor.execute(
            'UPDATE api_keys SET password_hash = ? WHERE api_key = ?',
            (password_hash, api_key.strip())
        )
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def admin_set_user_tier(self, api_key: str, tier_id: int) -> bool:
        """Nastaví tier_id uživatele (pouze dropdown Tier v Admin)."""
        if not api_key or not str(api_key).strip():
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE api_keys SET tier_id = ? WHERE api_key = ?', (tier_id if tier_id else None, api_key.strip()))
        ok = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return ok

    def admin_update_license_features(self, api_key: str, max_batch_size=None,
                                       allow_signatures=None, allow_timestamp=None,
                                       allow_excel_export=None, max_devices=None) -> bool:
        """Aktualizuje feature flags a max_devices licence."""
        if not api_key or not str(api_key).strip():
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        updates = []
        values = []
        updates.append('max_batch_size = ?')
        values.append(None if max_batch_size is None else (max_batch_size if max_batch_size >= 0 else None))
        if allow_signatures is not None:
            updates.append('allow_signatures = ?')
            values.append(1 if allow_signatures else 0)
        if allow_timestamp is not None:
            updates.append('allow_timestamp = ?')
            values.append(1 if allow_timestamp else 0)
        if allow_excel_export is not None:
            updates.append('allow_excel_export = ?')
            values.append(1 if allow_excel_export else 0)
        if max_devices is not None and max_devices >= 0:
            updates.append('max_devices = ?')
            values.append(max_devices)
        if not updates:
            conn.close()
            return True
        values.append(api_key.strip())
        cursor.execute(
            f'UPDATE api_keys SET {", ".join(updates)} WHERE api_key = ?',
            values
        )
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def admin_generate_license_key(self, user_name: str, email: str,
                                    tier: int, days: int = 365, password: str = None) -> str:
        """Vygeneruje nový licenční klíč (admin funkce). password = heslo pro přihlášení uživatele v agentovi (e-mail+heslo)."""
        prefix = ['sk_free_', 'sk_basic_', 'sk_pro_', 'sk_ent_'][min(tier, 3)]
        api_key = prefix + secrets.token_hex(16)

        success = self.create_api_key_with_license(
            api_key=api_key,
            user_name=user_name,
            email=email,
            license_tier=tier,
            license_days=days,
            password=password,
        )

        return api_key if success else None

    def admin_create_license_by_tier_id(self, user_name: str, email: str, tier_id: int,
                                         days: int = 365, password: str = None) -> str:
        """Vytvoří licenci s tier_id z DB (Free/Basic/Pro/Trial). Vrací api_key nebo None."""
        tier_row = self.get_tier_by_id(tier_id)
        if not tier_row:
            return None
        prefix = 'sk_tier_'
        api_key = prefix + secrets.token_hex(16)
        license_expires = (datetime.now() + timedelta(days=days)).isoformat() if days and days > 0 else None
        password_hash = self._hash_password(password) if password and str(password).strip() else None
        max_files = tier_row.get('max_files_limit', 10)
        max_devices = tier_row.get('max_devices', 1)
        allow_sig = 1 if tier_row.get('allow_signatures') else 0
        allow_ts = 1 if tier_row.get('allow_timestamp') else 0
        allow_excel = 1 if tier_row.get('allow_excel_export') else 0
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO api_keys (api_key, user_name, email, tier_id, license_expires,
                    password_hash, max_batch_size, max_devices, rate_limit_hour,
                    allow_signatures, allow_timestamp, allow_excel_export, license_tier, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 10, ?, ?, ?, 0, 1)
            ''', (api_key, user_name, email, tier_id, license_expires, password_hash,
                  max_files, max_devices, allow_sig, allow_ts, allow_excel))
            conn.commit()
            return api_key
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()


# Helper funkce pro generování API klíče
def generate_api_key():
    """Vygeneruje náhodný API klíč"""
    import secrets
    import string

    # Format: sk_test_<32 random characters>
    alphabet = string.ascii_lowercase + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(32))
    return f"sk_test_{random_part}"


# Test při spuštění
if __name__ == "__main__":
    db = Database('test.db')

    # Vygeneruj testovací klíč
    test_key = generate_api_key()
    print(f"Testovací API klíč: {test_key}")

    db.create_api_key(test_key, "Test User")
    print(f"API klíč vytvořen: {db.verify_api_key(test_key)}")

    # Test batch
    batch_id = db.create_batch(test_key, "Test Batch", "/home/user/documents")
    print(f"Batch vytvořen: {batch_id}")

    # Testovací data
    test_result = {
        'file_name': 'test.pdf',
        'file_hash': 'abc123',
        'file_size': 12345,
        'folder': 'subfolder',
        'relative_path': 'subfolder/test.pdf',
        'processed_at': datetime.now().isoformat(),
        'success': True,
        'results': {
            'pdf_format': {'is_pdf_a3': True, 'exact_version': 'PDF/A-3b'},
            'signatures': [{'valid': True}]
        }
    }

    success, result_id = db.save_result(test_key, test_result, batch_id)
    print(f"Výsledek uložen: {success}, ID: {result_id}")

    # Update batch stats
    db.update_batch_stats(batch_id)

    # Get batches
    batches = db.get_batches()
    print(f"Počet batchů: {len(batches)}")

    # Statistiky
    stats = db.get_statistics(test_key)
    print(f"Statistiky: {stats}")
