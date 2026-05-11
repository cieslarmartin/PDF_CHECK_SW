#!/usr/bin/env python3
# Nastaví admin přihlášení na: admin / admin
# Spuštění na PA: cd ~/pdf-dokucheck-web/v42 && python nastav_admin_admin.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import Database

db = Database()
# Pokud už existuje účet s emailem "admin", nastavíme mu heslo "admin"
user = db.get_admin_by_email('admin')
if user:
    db.update_admin_user(
        user['id'],
        password='admin',
        otp_email=(user.get('otp_email') or '').strip() or 'cieslar@dokucheck.cz',
    )
    print('OK: Heslo pro admin nastaveno na "admin", doplněn otp_email pokud chyběl.')
else:
    success, msg = db.create_admin_user(
        email='admin',
        password='admin',
        role='ADMIN',
        display_name='Admin',
        otp_email='cieslar@dokucheck.cz',
    )
    if success:
        print('OK: Admin účet vytvořen. Přihlášení: admin / admin')
    else:
        print('CHYBA:', msg)
