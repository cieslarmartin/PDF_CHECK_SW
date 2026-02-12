#!/usr/bin/env python3
# init_test_data.py
# Inicializace testovacích dat pro PDF DokuCheck Admin systém
# Build 41 | © 2025 Ing. Martin Cieślar
#
# Spuštění: python init_test_data.py
#
# Tento skript vytvoří:
# - Admin účet: admin@pdfcheck.cz / admin123
# - Testovací licence pro Basic tier
# - Testovací licence pro Pro tier
# - Enterprise licenci pro admina

import sys
import os

# Přidej aktuální složku do path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import Database
from license_config import LicenseTier

def init_test_data():
    """
    Inicializuje testovací data pro admin systém
    """
    print("=" * 60)
    print("  PDF DokuCheck - Inicializace testovacich dat")
    print("=" * 60)
    print()

    db = Database()
    results = {}

    # 1. Vytvoř admin účet (přihlášení: admin / admin)
    print("[1/4] Vytvářím admin účet...")
    success, msg = db.create_admin_user(
        email='admin',
        password='admin',
        role='ADMIN',
        display_name='Admin'
    )
    if success:
        print(f"      OK: Admin účet vytvořen")
        results['admin_email'] = 'admin'
        results['admin_password'] = 'admin'
    else:
        print(f"      INFO: {msg}")
        results['admin_email'] = 'admin'
        results['admin_password'] = 'admin'

    # 2. Vytvoř Basic testovací licenci
    print("[2/4] Vytvářím Basic testovací licenci...")
    api_key_basic = db.admin_generate_license_key(
        user_name='Tester Basic',
        email='tester-basic@test.cz',
        tier=LicenseTier.BASIC,
        days=365
    )
    if api_key_basic:
        print(f"      OK: Basic licence vytvořena")
        results['basic_email'] = 'tester-basic@test.cz'
        results['basic_key'] = api_key_basic
    else:
        print(f"      CHYBA: Nepodařilo se vytvořit Basic licenci")
        # Zkus najít existující
        existing = db.get_user_license(results.get('basic_key', ''))
        if existing:
            results['basic_key'] = existing['api_key']

    # 3. Vytvoř Pro testovací licenci
    print("[3/4] Vytvářím Pro testovací licenci...")
    api_key_pro = db.admin_generate_license_key(
        user_name='Tester Pro',
        email='tester-pro@test.cz',
        tier=LicenseTier.PRO,
        days=365
    )
    if api_key_pro:
        print(f"      OK: Pro licence vytvořena")
        results['pro_email'] = 'tester-pro@test.cz'
        results['pro_key'] = api_key_pro
    else:
        print(f"      CHYBA: Nepodařilo se vytvořit Pro licenci")

    # 4. Vytvoř Enterprise licenci pro admina
    print("[4/4] Vytvářím Enterprise licenci pro admina...")
    api_key_ent = db.admin_generate_license_key(
        user_name='Admin Enterprise',
        email='admin',
        tier=LicenseTier.ENTERPRISE,
        days=365
    )
    if api_key_ent:
        print(f"      OK: Enterprise licence vytvořena")
        results['enterprise_email'] = 'admin'
        results['enterprise_key'] = api_key_ent
    else:
        print(f"      CHYBA: Nepodařilo se vytvořit Enterprise licenci")

    # Výpis výsledků
    print()
    print("=" * 60)
    print("  TESTOVACÍ DATA VYTVOŘENA")
    print("=" * 60)
    print()
    print("  ADMIN PŘIHLÁŠENÍ:")
    print(f"    Email:    {results.get('admin_email', 'N/A')}")
    print(f"    Heslo:    {results.get('admin_password', 'N/A')}")
    print(f"    URL:      https://www.dokucheck.cz/login")
    print()
    print("  TESTOVACÍ LICENCE:")
    print()
    print("  [BASIC]")
    print(f"    Email:    {results.get('basic_email', 'N/A')}")
    print(f"    API Key:  {results.get('basic_key', 'N/A')}")
    print()
    print("  [PRO]")
    print(f"    Email:    {results.get('pro_email', 'N/A')}")
    print(f"    API Key:  {results.get('pro_key', 'N/A')}")
    print()
    print("  [ENTERPRISE]")
    print(f"    Email:    {results.get('enterprise_email', 'N/A')}")
    print(f"    API Key:  {results.get('enterprise_key', 'N/A')}")
    print()
    print("=" * 60)
    print()
    print("  POZNÁMKA: Tyto údaje si uložte!")
    print("  Admin dashboard: /login → /admin")
    print()

    return results


if __name__ == '__main__':
    try:
        results = init_test_data()
    except Exception as e:
        print(f"\nCHYBA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
