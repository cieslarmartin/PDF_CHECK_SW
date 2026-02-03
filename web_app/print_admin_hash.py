#!/usr/bin/env python3
"""
Jednorázový skript: vypíše email a password_hash z tabulky admin_users.
Spusť z složky web_app:  python print_admin_hash.py
Pokud přihlášení nefunguje, zkontroluj že hash odpovídá heslu 'admin123'
(v init_test_data je heslo admin123 pro admin@pdfcheck.cz).
"""
import os
import sys

# CWD = web_app
basedir = os.path.dirname(os.path.abspath(__file__))
os.chdir(basedir)
sys.path.insert(0, basedir)

from database import Database

db = Database()
conn = db.get_connection()
cur = conn.cursor()
cur.execute('SELECT id, email, password_hash, role, is_active FROM admin_users')
rows = cur.fetchall()
conn.close()

if not rows:
    print('Tabulka admin_users je prázdná.')
else:
    for row in rows:
        r = dict(row)
        print(f"id: {r['id']} | email: {r['email']} | role: {r['role']} | is_active: {r['is_active']}")
        print(f"password_hash: {r['password_hash']}")
        print('---')
