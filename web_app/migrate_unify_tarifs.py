#!/usr/bin/env python3
# migrate_unify_tarifs.py – sjednotí tarify: standard → pro v pricing_tarifs a pending_orders.
# Použití: cd web_app && python migrate_unify_tarifs.py

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from database import Database
from settings_loader import _normalize_pricing_tarifs_dict, DEFAULT_PRICING_TARIFS


def run():
    db = Database()

    # 1) pricing_tarifs v global_settings
    raw = db.get_setting_json("pricing_tarifs", None)
    if isinstance(raw, dict):
        normalized = _normalize_pricing_tarifs_dict(raw)
        if normalized != raw:
            db.set_global_setting("pricing_tarifs", normalized)
            print("pricing_tarifs: standard → pro, doplněny chybějící klíče.")
        else:
            print("pricing_tarifs: již sjednoceno.")
    else:
        db.set_global_setting("pricing_tarifs", DEFAULT_PRICING_TARIFS)
        print("pricing_tarifs: nastaven výchozí ceník (basic, pro, firemni).")

    # 2) pending_orders.tarif
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM pending_orders WHERE LOWER(TRIM(tarif)) = 'standard'")
    n = cur.fetchone()[0]
    if n:
        cur.execute("UPDATE pending_orders SET tarif = 'pro' WHERE LOWER(TRIM(tarif)) = 'standard'")
        conn.commit()
        print(f"pending_orders: {n} záznamů standard → pro.")
    else:
        print("pending_orders: žádný záznam standard.")
    conn.close()

    print("Hotovo.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
