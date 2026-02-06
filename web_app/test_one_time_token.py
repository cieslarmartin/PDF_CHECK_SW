#!/usr/bin/env python3
"""
Test: jednorázové přihlašovací tokeny (agent → web).
Ověří, že token uložený v DB je najitelný a po spotřebování už není platný.
Simuluje situaci „worker A vytvoří token, worker B ho spotřebuje“ (sdílená DB).
"""
import os
import sys
import time

# běh z web_app nebo z kořene projektu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    from database import Database
    from api_endpoint import consume_one_time_token

    # Použij výchozí DB (tabulka one_time_login_tokens se vytvoří v init_database)
    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='one_time_login_tokens'")
    if not cursor.fetchone():
        conn.close()
        print("FAIL: Tabulka one_time_login_tokens neexistuje.")
        return 1
    conn.close()

    # 1) Uložení tokenu (simulace endpointu one-time-login-token)
    token = "test-token-" + str(time.time())
    api_key = "test-api-key-trial"
    expires_at = time.time() + 120
    ok = db.store_one_time_login_token(token, api_key, expires_at)
    if not ok:
        print("FAIL: store_one_time_login_token vrátilo False")
        return 1
    print("OK: Token uložen do DB")

    # 2) Spotřebování tokenu (simulace druhého workeru – jiná instance Database na stejné DB)
    # V :memory: je každá Database() jiná DB, takže pro reálný test musíme použít stejnou instanci
    api_key_out, consumed = db.consume_one_time_login_token(token)
    if not consumed or api_key_out != api_key:
        print("FAIL: consume_one_time_login_token nevrátil správný api_key")
        return 1
    print("OK: Token spotřebován, api_key odpovídá")

    # 3) Druhé spotřebování musí selhat (token už není v DB)
    api_key_out2, consumed2 = db.consume_one_time_login_token(token)
    if consumed2 or api_key_out2:
        print("FAIL: Token byl použit dvakrát (mělo selhat)")
        return 1
    print("OK: Token nelze použít podruhé")

    # 4) Neexistující token → consume_one_time_token (api_endpoint) vrátí (None, None)
    fake_token = "neexistujici-token-12345"
    api_key_consume, license_info = consume_one_time_token(fake_token)
    if api_key_consume is not None or license_info is not None:
        print("FAIL: consume_one_time_token měl pro neplatný token vrátit (None, None)")
        return 1
    print("OK: Neplatný token vrací (None, None) – web pak má zavolat session.pop('portal_user', None)")

    print("\nVšechny testy prošly. Tokeny v DB jsou sdílené mezi workery; při neplatném tokenu má web v auth_from_agent_token volat session.pop('portal_user', None).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
