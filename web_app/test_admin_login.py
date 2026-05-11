#!/usr/bin/env python3
"""
Test přihlášení admina a přístupu k dashboardu.
Spusť z složky web_app:  python test_admin_login.py

Použití:
  - Přihlášení: admin / admin, poté šestimístný kód z e-mailu (viz otp_email v DB).
  - Po dokončení obou kroků máte přístup k /admin (dashboard).
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
    DEFAULT_ADMIN_LOGIN,
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
    success, result = db.verify_admin_password_step(email, password)

    if success:
        log("OK – První krok (heslo) funguje.")
        log(f"  Uživatel: {result.get('display_name', email)}, role: {result.get('role')}")
        log(f"  OTP e-mail v DB: {result.get('otp_email') or '(stejný jako přihlašovací jméno – doplní ensure_default_admin)'}")
        log()
        log("Přístup k dashboardu:")
        log("  1. /login – jméno admin, heslo admin")
        log("  2. Kód z e-mailu na stránce /login/verify-code")
        log("  3. Poté /admin nebo /admin/dashboard")
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
