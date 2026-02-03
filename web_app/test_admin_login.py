#!/usr/bin/env python3
"""
Test přihlášení admina a přístupu k dashboardu.
Spusť z složky web_app:  python test_admin_login.py

Použití:
  - admin@admin.cz / admin
  - Po přihlášení na /login máte přístup k /admin (dashboard) a všem admin funkcím.
"""
import os
import sys

basedir = os.path.dirname(os.path.abspath(__file__))
os.chdir(basedir)
sys.path.insert(0, basedir)

from admin_routes import (
    ensure_default_admin,
    reset_default_admin_password,
    get_default_admin_credentials,
    DEFAULT_ADMIN_EMAIL,
    DEFAULT_ADMIN_PASSWORD,
)
from database import Database

def main():
    lines = []
    def log(s=''):
        lines.append(s)
        print(s)

    log("=== Test admin přístupu (dashboard) ===")
    log()

    ensure_default_admin()
    reset_default_admin_password()

    email, password = get_default_admin_credentials()
    log(f"Účet: {email}")
    log(f"Heslo: {password}")
    log()

    db = Database()
    success, result = db.verify_admin_login(email, password)

    if success:
        log("OK – Přihlášení funguje.")
        log(f"  Uživatel: {result.get('display_name', email)}, role: {result.get('role')}")
        log()
        log("Přístup k dashboardu a admin funkcím:")
        log("  1. Otevřete v prohlížeči: /login")
        log("  2. Zadejte e-mail: admin@admin.cz")
        log("  3. Zadejte heslo: admin")
        log("  4. Po přihlášení: /admin nebo /admin/dashboard")
        log("  (Licence, Tiery, Čeká na platbu, Trial, Logy, Nastavení, Změna hesla, atd.)")
    else:
        log("CHYBA – Přihlášení selhalo.")
        log(f"  Důvod: {result}")

    result_path = os.path.join(basedir, 'test_admin_login_result.txt')
    with open(result_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    log()
    log(f"(Výsledek zapsán do {result_path})")


if __name__ == '__main__':
    main()
