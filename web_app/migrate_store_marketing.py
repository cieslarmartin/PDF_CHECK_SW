#!/usr/bin/env python3
# migrate_store_marketing.py – vypne pilotní upozornění a doplní Store marketing do DB (jednorázově na PA).
# Použití: cd web_app && python migrate_store_marketing.py

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from database import Database
from settings_loader import (
    DEFAULT_DOWNLOAD_WHATS_NEW,
    DEFAULT_LANDING_UPDATES,
    DEFAULT_TOP_PROMO_BAR,
)

STORE_UPDATE_MONTH = "07/2026"


def run():
    db = Database()
    db.set_global_setting("show_pilot_notice", "0")
    db.set_global_setting("pilot_notice_text", "")

    promo = db.get_setting_json("top_promo_bar", None)
    if not isinstance(promo, dict) or not (promo.get("text") or "").strip():
        db.set_global_setting("top_promo_bar", json.dumps(DEFAULT_TOP_PROMO_BAR, ensure_ascii=False))
        print("Nastaven top_promo_bar (Microsoft Store).")
    else:
        print("top_promo_bar už má text – ponechán.")

    whats_new = (db.get_global_setting("download_whats_new", "") or "").strip()
    if not whats_new:
        db.set_global_setting("download_whats_new", DEFAULT_DOWNLOAD_WHATS_NEW)
        print("Doplněn download_whats_new.")
    else:
        print("download_whats_new už existuje – ponechán.")

    updates = db.get_setting_json("landing_updates", None)
    if not isinstance(updates, list):
        updates = []
    has_store = any(
        STORE_UPDATE_MONTH in str(u.get("month", ""))
        or "microsoft store" in str(u.get("title", "")).lower()
        for u in updates
        if isinstance(u, dict)
    )
    if not has_store:
        store_entry = DEFAULT_LANDING_UPDATES[0]
        updates.insert(0, store_entry)
        db.set_global_setting("landing_updates", json.dumps(updates, ensure_ascii=False))
        print("Přidána novinka Microsoft Store do landing_updates.")
    else:
        print("landing_updates už obsahuje Store – ponecháno.")

    print("Migrace Store marketingu dokončena.")
    return True


if __name__ == "__main__":
    run()
