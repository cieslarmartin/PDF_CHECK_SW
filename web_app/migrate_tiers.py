#!/usr/bin/env python3
# migrate_tiers.py
# DATABASE UPGRADE: Tier-Based License System
# Tiery: Trial (7 dní, max 100 kontrol, vše otevřené), Basic (blokované filtry + Excel/CSV), Pro (vše), Unlimited/God (vše, admin).
# Spusť: cd ~/web_app && python migrate_tiers.py
# © 2025 Ing. Martin Cieślar

import os
import sqlite3
import hashlib
import secrets

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'pdfcheck_results.db')

DEMO_TRIAL_EMAIL = 'free@trial.app'
DEMO_TRIAL_PASSWORD = 'free'  # pro tlačítko "Vyzkoušet zdarma" v agentovi (CRITICAL: musí odpovídat license.py)


def _hash_password(password: str) -> str:
    """Stejný format jako database.Database._hash_password."""
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
    return f"{salt}${h}"


def run():
    if not os.path.exists(db_path):
        print(f"CHYBA: Databáze nenalezena: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1) Tabulka license_tiers (+ allow_advanced_filters pro omezení filtrů u Basic)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS license_tiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            max_files_limit INTEGER NOT NULL DEFAULT 10,
            allow_signatures BOOLEAN DEFAULT 0,
            allow_timestamp BOOLEAN DEFAULT 0,
            allow_excel_export BOOLEAN DEFAULT 0,
            allow_advanced_filters BOOLEAN DEFAULT 0,
            max_devices INTEGER NOT NULL DEFAULT 1
        )
    ''')
    cur.execute("PRAGMA table_info(license_tiers)")
    tier_cols = {r[1] for r in cur.fetchall()}
    if 'allow_advanced_filters' not in tier_cols:
        cur.execute("ALTER TABLE license_tiers ADD COLUMN allow_advanced_filters BOOLEAN DEFAULT 0")
        print("Přidán sloupec license_tiers.allow_advanced_filters.")
    cur.execute("SELECT COUNT(*) FROM license_tiers")
    count = cur.fetchone()[0]
    # (id, name, max_files, allow_sig, allow_ts, allow_excel, allow_filters, max_dev)
    default_tiers = [
        (1, 'Trial', 100, 1, 1, 1, 1, 1),
        (2, 'Basic', 500, 1, 1, 0, 0, 1),   # Filtry i export blokované
        (3, 'Pro', 99999, 1, 1, 1, 1, 3),
        (4, 'Unlimited', 99999, 1, 1, 1, 1, 10),
    ]
    if count == 0:
        cur.executemany(
            '''INSERT INTO license_tiers (id, name, max_files_limit, allow_signatures, allow_timestamp, allow_excel_export, allow_advanced_filters, max_devices)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            default_tiers
        )
        print("Vloženy výchozí tier definice včetně allow_advanced_filters.")
    else:
        for tier_id, name, max_files, allow_sig, allow_ts, allow_excel, allow_filters, max_dev in default_tiers:
            cur.execute('''
                UPDATE license_tiers SET name=?, max_files_limit=?, allow_signatures=?, allow_timestamp=?, allow_excel_export=?, allow_advanced_filters=?, max_devices=?
                WHERE id=?
            ''', (name, max_files, allow_sig, allow_ts, allow_excel, allow_filters, max_dev, tier_id))
        cur.execute("DELETE FROM license_tiers WHERE id > 4")
        print("Tier definice synchronizovány (včetně allow_advanced_filters).")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_license_tiers_name ON license_tiers(name)")

    # 2) Sloupce tier_id a password_hash v api_keys
    cur.execute("PRAGMA table_info(api_keys)")
    cols = {r[1] for r in cur.fetchall()}
    if 'tier_id' not in cols:
        cur.execute("ALTER TABLE api_keys ADD COLUMN tier_id INTEGER REFERENCES license_tiers(id)")
        print("Přidán sloupec api_keys.tier_id.")
    if 'password_hash' not in cols:
        try:
            cur.execute("ALTER TABLE api_keys ADD COLUMN password_hash TEXT")
            print("Přidán sloupec api_keys.password_hash.")
        except sqlite3.OperationalError:
            pass

    # 3) Zpětné vyplnění tier_id z license_tier (0->1, 1->2, 2->3, 3->4)
    cur.execute("UPDATE api_keys SET tier_id = license_tier + 1 WHERE tier_id IS NULL AND license_tier IS NOT NULL")
    updated = cur.rowcount
    if updated:
        print(f"Zpětně vyplněno tier_id u {updated} záznamů (podle license_tier).")

    # 4) Demo Trial uživatel: vytvoř nebo propoj s Trial tierem (heslo: demo123)
    cur.execute("SELECT id FROM license_tiers WHERE name = 'Trial'")
    row = cur.fetchone()
    trial_id = row[0] if row else None
    cur.execute("PRAGMA table_info(api_keys)")
    api_keys_cols = {r[1] for r in cur.fetchall()}
    if trial_id is not None:
        cur.execute("SELECT api_key FROM api_keys WHERE LOWER(TRIM(email)) = LOWER(TRIM(?))", (DEMO_TRIAL_EMAIL,))
        existing = cur.fetchone()
        if existing:
            cur.execute("UPDATE api_keys SET tier_id = ? WHERE LOWER(TRIM(email)) = LOWER(TRIM(?))", (trial_id, DEMO_TRIAL_EMAIL))
            if 'password_hash' in api_keys_cols:
                cur.execute("UPDATE api_keys SET password_hash = ? WHERE LOWER(TRIM(email)) = LOWER(TRIM(?))",
                            (_hash_password(DEMO_TRIAL_PASSWORD), DEMO_TRIAL_EMAIL))
            print(f"Uživatel {DEMO_TRIAL_EMAIL} propojen s tier Trial (heslo: {DEMO_TRIAL_PASSWORD}).")
        else:
            api_key = 'sk_trial_' + secrets.token_hex(16)
            password_hash = _hash_password(DEMO_TRIAL_PASSWORD)
            if 'tier_id' in api_keys_cols and 'password_hash' in api_keys_cols:
                cur.execute('''
                    INSERT INTO api_keys (api_key, user_name, email, tier_id, password_hash, license_tier, max_devices, rate_limit_hour, is_active)
                    VALUES (?, ?, ?, ?, ?, 0, 999999, 10, 1)
                ''', (api_key, 'Trial Demo', DEMO_TRIAL_EMAIL, trial_id, password_hash))
                print(f"Vytvořen demo uživatel {DEMO_TRIAL_EMAIL} (tier Trial, heslo: {DEMO_TRIAL_PASSWORD}).")
            else:
                cur.execute('''
                    INSERT INTO api_keys (api_key, user_name, email, license_tier, max_devices, rate_limit_hour, is_active)
                    VALUES (?, ?, ?, 0, 999999, 10, 1)
                ''', (api_key, 'Trial Demo', DEMO_TRIAL_EMAIL))
                if 'tier_id' in api_keys_cols:
                    cur.execute("UPDATE api_keys SET tier_id = ? WHERE email = ?", (trial_id, DEMO_TRIAL_EMAIL))
                print(f"Vytvořen demo uživatel {DEMO_TRIAL_EMAIL} (tier Trial).")

    # 4) global_settings
    cur.execute('''
        CREATE TABLE IF NOT EXISTS global_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    for key, default in [('maintenance_mode', '0'), ('allow_new_registrations', '1')]:
        cur.execute("SELECT 1 FROM global_settings WHERE key = ?", (key,))
        if not cur.fetchone():
            cur.execute("INSERT INTO global_settings (key, value) VALUES (?, ?)", (key, default))
            print(f"Vloženo global_settings.{key} = {default}.")

    conn.commit()
    conn.close()
    print("\nMigrace tierů dokončena.")
    return True


if __name__ == '__main__':
    run()
