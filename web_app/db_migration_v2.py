#!/usr/bin/env python3
# db_migration_v2.py
# Migrace schématu pro PDF DokuCheck – user_devices, feature toggles (allow_excel_export, max_devices).
# Spusť na PythonAnywhere v konzoli: cd ~/web_app && python db_migration_v2.py
# © 2025 Ing. Martin Cieślar

import os
import sqlite3

# Cesta k DB – stejná jako v aplikaci (absolutní kvůli PA)
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'pdfcheck_results.db')


def run_migration():
    if not os.path.exists(db_path):
        print(f"CHYBA: Databáze nenalezena: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    changes = []

    # 1) Tabulka user_devices (pro device locking / analytics)
    cursor.execute("""
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
    """)
    if cursor.rowcount != -1:
        pass  # CREATE TABLE IF NOT EXISTS nevrací rowcount smysluplně
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_devices'")
    if cursor.fetchone():
        changes.append("Tabulka user_devices existuje nebo byla vytvořena.")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_devices_user_id ON user_devices(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_devices_machine_id ON user_devices(machine_id)")
    changes.append("Indexy user_devices zkontrolovány.")

    # 2) Chybějící sloupce v api_keys (licence)
    cursor.execute("PRAGMA table_info(api_keys)")
    existing = {row[1] for row in cursor.fetchall()}

    columns_to_add = [
        ("max_devices", "INTEGER DEFAULT 1"),
        ("allow_signatures", "BOOLEAN DEFAULT 1"),
        ("allow_timestamp", "BOOLEAN DEFAULT 1"),
        ("allow_excel_export", "BOOLEAN DEFAULT 1"),
        ("max_batch_size", "INTEGER"),
        ("email", "TEXT"),
        ("password_hash", "TEXT"),
    ]

    for col_name, col_type in columns_to_add:
        if col_name not in existing:
            try:
                cursor.execute(f"ALTER TABLE api_keys ADD COLUMN {col_name} {col_type}")
                changes.append(f"Přidán sloupec api_keys.{col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    changes.append(f"Sloupec api_keys.{col_name} již existuje.")
                else:
                    print(f"Varování: api_keys.{col_name}: {e}")

    conn.commit()
    conn.close()

    for line in changes:
        print(line)
    print("\nMigrace v2 dokončena.")
    return True


if __name__ == "__main__":
    run_migration()
