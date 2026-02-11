#!/usr/bin/env python3
# db_migration_trial_activity.py
# Migrace: web_trial_ip_usage, activity_log (Trial web, sjednocené logy).
# Spusť: cd web_app && python db_migration_trial_activity.py
# © 2025 Ing. Martin Cieślar

import os
import sqlite3

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'pdfcheck_results.db')


def run_migration():
    if not os.path.exists(db_path):
        print(f"CHYBA: Databáze nenalezena: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    changes = []

    # trial_usage (Agent – machine_id) – měla by existovat
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trial_usage (
            machine_id TEXT PRIMARY KEY,
            total_files INTEGER NOT NULL DEFAULT 0,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trial_usage_last_seen ON trial_usage(last_seen)")
    changes.append("trial_usage (Agent) – OK")

    # web_trial_ip_usage (Web – IP, max 3 batche/24h)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS web_trial_ip_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            usage_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_web_trial_ip_usage ON web_trial_ip_usage(ip_address, usage_timestamp)")
    changes.append("web_trial_ip_usage – OK")

    # activity_log (sjednocený log: Web Trial, Agent, Registrovaný)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source_type TEXT NOT NULL,
            file_count INTEGER NOT NULL DEFAULT 0,
            api_key TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_log_timestamp ON activity_log(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_log_ip ON activity_log(ip_address)")
    changes.append("activity_log – OK")

    conn.commit()
    conn.close()

    for c in changes:
        print(f"  {c}")
    print("Migrace trial/activity dokončena.")
    return True


if __name__ == '__main__':
    run_migration()
