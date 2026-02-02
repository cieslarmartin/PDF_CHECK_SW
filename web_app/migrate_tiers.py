#!/usr/bin/env python3
# migrate_tiers.py
# Migrace na tier-based systém: vytvoří license_tiers, vloží výchozí řádky,
# přidá tier_id do api_keys a zpětně vyplní z license_tier (0->1, 1->2, 2->3, 3->4).
# Vytvoří global_settings a vloží výchozí hodnoty.
# Spusť na PythonAnywhere: cd ~/web_app && python migrate_tiers.py
# © 2025 Ing. Martin Cieślar

import os
import sqlite3

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'pdfcheck_results.db')


def run():
    if not os.path.exists(db_path):
        print(f"CHYBA: Databáze nenalezena: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1) Tabulka license_tiers
    cur.execute('''
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
    cur.execute("SELECT COUNT(*) FROM license_tiers")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            '''INSERT INTO license_tiers (id, name, max_files_limit, allow_signatures, allow_timestamp, allow_excel_export, max_devices)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            [
                (1, 'Free', 10, 0, 0, 0, 1),
                (2, 'Basic', 100, 1, 1, 1, 2),
                (3, 'Pro', 1000, 1, 1, 1, 4),
                (4, 'Enterprise', 99999, 1, 1, 1, 10),
            ]
        )
        print("Vloženy výchozí tier definice: Free, Basic, Pro, Enterprise.")
    else:
        print("Tabulka license_tiers již obsahuje data.")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_license_tiers_name ON license_tiers(name)")

    # 2) Sloupec tier_id v api_keys
    cur.execute("PRAGMA table_info(api_keys)")
    cols = {r[1] for r in cur.fetchall()}
    if 'tier_id' not in cols:
        cur.execute("ALTER TABLE api_keys ADD COLUMN tier_id INTEGER REFERENCES license_tiers(id)")
        print("Přidán sloupec api_keys.tier_id.")
    else:
        print("Sloupec api_keys.tier_id již existuje.")

    # 3) Zpětné vyplnění tier_id z license_tier (0->1, 1->2, 2->3, 3->4)
    cur.execute("UPDATE api_keys SET tier_id = license_tier + 1 WHERE tier_id IS NULL AND license_tier IS NOT NULL")
    updated = cur.rowcount
    if updated:
        print(f"Zpětně vyplněno tier_id u {updated} záznamů (podle license_tier).")

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
