#!/usr/bin/env python3
"""
EMERGENCY FIX: Nastaví v DB admin účet admin@admin.cz s heslem 'admin'.
1. Smaže existující záznam pro admin@admin.cz v admin_users.
2. Vloží nový záznam s e-mailem, rolí ADMIN a zahashovaným heslem (PBKDF2-HMAC-SHA256).
3. Ověří přihlášení voláním verify_admin_login('admin@admin.cz', 'admin').
Spusť z web_app:  python force_fix_admin.py
"""
import os
import sys

basedir = os.path.dirname(os.path.abspath(__file__))
os.chdir(basedir)
sys.path.insert(0, basedir)

def main():
    from database import Database

    db = Database()
    conn = db.get_connection()
    cur = conn.cursor()

    # 1. Smazat existující záznam pro admin@admin.cz
    cur.execute("DELETE FROM admin_users WHERE email = ?", ('admin@admin.cz',))
    deleted = cur.rowcount
    conn.commit()

    # 2. Zahashovat heslo 'admin' stejnou metodou jako Database (PBKDF2-HMAC-SHA256)
    password_hash = db._hash_password('admin')

    # 3. Vložit nový záznam
    cur.execute('''
        INSERT INTO admin_users (email, password_hash, role, display_name, is_active)
        VALUES (?, ?, ?, ?, 1)
    ''', ('admin@admin.cz', password_hash, 'ADMIN', 'Admin'))
    conn.commit()
    conn.close()

    # 4. Test: verify_admin_login
    success, result = db.verify_admin_login('admin@admin.cz', 'admin')

    print("force_fix_admin.py:")
    print(f"  Smazáno záznamů: {deleted}")
    print(f"  Vložen nový admin: admin@admin.cz / admin")
    print(f"  verify_admin_login('admin@admin.cz', 'admin'): {'OK (True)' if success else 'CHYBA (False)'}")
    if success:
        print(f"  Uživatel: {result.get('display_name')}, role: {result.get('role')}")
    else:
        print(f"  Důvod: {result}")
    print()
    # Zapsat výsledek do souboru pro ověření
    out_path = os.path.join(basedir, 'force_fix_admin_result.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("OK\n" if success else "FAIL\n")
        f.write(f"verify_admin_login: {success}\n")
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
