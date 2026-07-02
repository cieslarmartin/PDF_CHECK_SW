#!/usr/bin/env python3
# migrate_firemni_tier.py – založí tier „Firemní“ (5 zařízení, funkce jako Pro) a doplní cenu do pricing_tarifs.
# Použití: cd web_app && python migrate_firemni_tier.py

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from database import Database

FIREMNI_NAME = "Firemní"
FIREMNI_MAX_DEVICES = 5
FIREMNI_AMOUNT_CZK = 6360  # 4 × 1590 (5. zařízení zdarma)

FIREMNI_CHECKOUT_FEATURES = (
    "Vše z tarifu Ateliér (PRO)\n"
    "Až 5 zařízení pod jedním účtem\n"
    "Jedno přihlášení pro celou firmu\n"
    "Kontrola elektronických podpisů a časových razítek\n"
    "Export do Excel (XLS)\n"
    "Pokročilé filtry chyb"
)


def run():
    db = Database()

    # 1. Tier Firemní – limity zkopírované z Pro, jen max_devices=5
    existing = db.get_tier_by_name(FIREMNI_NAME)
    if existing:
        print(f"Tier „{FIREMNI_NAME}“ už existuje (id={existing.get('id')}) – ponechán.")
    else:
        pro = db.get_tier_by_name("Pro") or {}
        tier_id, err = db.insert_tier(
            name=FIREMNI_NAME,
            max_files_limit=pro.get("max_files_limit", 99999),
            allow_signatures=bool(pro.get("allow_signatures", 1)),
            allow_timestamp=bool(pro.get("allow_timestamp", 1)),
            allow_excel_export=bool(pro.get("allow_excel_export", 1)),
            allow_advanced_filters=bool(pro.get("allow_advanced_filters", 1)),
            max_devices=FIREMNI_MAX_DEVICES,
            daily_files_limit=pro.get("daily_files_limit"),
            rate_limit_hour=pro.get("rate_limit_hour"),
            max_file_size_mb=pro.get("max_file_size_mb"),
            checkout_features=FIREMNI_CHECKOUT_FEATURES,
        )
        if tier_id:
            print(f"Vytvořen tier „{FIREMNI_NAME}“ (id={tier_id}, max_devices={FIREMNI_MAX_DEVICES}, limity z Pro).")
        else:
            print(f"CHYBA: tier se nepodařilo vytvořit: {err}")
            return 1

    # 2. Cena v pricing_tarifs (jen pokud klíč firemni chybí – uloženou cenu nepřepisovat)
    pricing = db.get_setting_json("pricing_tarifs", None)
    if not isinstance(pricing, dict):
        print("pricing_tarifs v DB není – cena se doplní automaticky z výchozích hodnot (settings_loader).")
    elif "firemni" in pricing:
        print(f"pricing_tarifs.firemni už existuje ({pricing['firemni']}) – ponechán.")
    else:
        pricing["firemni"] = {"label": "FIREMNÍ", "amount_czk": FIREMNI_AMOUNT_CZK}
        db.set_global_setting("pricing_tarifs", pricing)
        print(f"Doplněn pricing_tarifs.firemni = {FIREMNI_AMOUNT_CZK} Kč/rok.")

    print("Hotovo.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
