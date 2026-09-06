# -*- coding: utf-8 -*-
"""
Automatický test mobilního API (/api/mobile/v1) proti lokální Flask instanci.

Spuštění (z web_app):
    .venv\\Scripts\\python.exe tests\\test_mobile_api.py

Test pracuje na KOPII databáze (pdfcheck_results.db se nemění), e-maily zachytává
monkeypatchem místo SMTP. Prochází: přihlášení + OTP + token, odvolání zařízení,
dashboard, CRUD licencí, zařízení, fakturace, objednávky, faktury, tarify, trial,
IP blokace, logy, obsah, nastavení.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import traceback

# Windows konzole je cp1250 – bez toho spadne výpis českých znaků a šipek
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
WEB_APP = os.path.dirname(HERE)
sys.path.insert(0, WEB_APP)
os.chdir(WEB_APP)

# --- Kopie DB (Database používá absolutní cestu web_app/pdfcheck_results.db) -------------
import database as database_mod  # noqa: E402

_tmpdir = tempfile.mkdtemp(prefix='dc_mobile_test_')
_test_db = os.path.join(_tmpdir, 'pdfcheck_results.db')
shutil.copyfile(database_mod._default_db_path, _test_db)
database_mod._default_db_path = _test_db
database_mod.db_path = _test_db

os.environ.setdefault('BASE_URL', 'http://localhost')

# Faktury z testu ukládat do dočasné složky, ne do web_app/data/invoices
_invoices_dir = os.path.join(_tmpdir, 'invoices')
os.makedirs(_invoices_dir, exist_ok=True)
database_mod.Database().set_global_setting('invoices_dir', _invoices_dir)

import pdf_check_web_main as main_mod  # noqa: E402
import email_sender  # noqa: E402
import admin_routes  # noqa: E402

SENT = []


def _fake_send_email(to_email, subject, body_plain, append_footer=True):
    SENT.append({'to': to_email, 'subject': subject, 'body': body_plain})
    return True


def _fake_send_with_attachment(to_email, subject, body_plain, attachment_path=None, attachment_filename=None,
                               append_footer=True, body_html=None):
    SENT.append({'to': to_email, 'subject': subject, 'body': body_plain, 'attachment': attachment_path})
    return True


email_sender.send_email = _fake_send_email
email_sender.send_email_with_attachment = _fake_send_with_attachment
email_sender.notify_admin = lambda subject, body: True
email_sender.send_order_notification_to_admin = lambda *a, **k: True

app = main_mod.app
app.config['TESTING'] = True
client = app.test_client()

PASSED = []
FAILED = []


def check(name, cond, detail=''):
    if cond:
        PASSED.append(name)
        print('  OK   ', name)
    else:
        FAILED.append((name, detail))
        print('  FAIL ', name, '->', detail)


def otp_from_mail():
    for m in reversed(SENT):
        if 'kód' in (m['subject'] or '').lower() or 'kod' in (m['subject'] or '').lower():
            import re
            mm = re.search(r'(\d{6})', m['body'])
            if mm:
                return mm.group(1)
    return None


TOKEN = None


def api(method, path, json_body=None, data=None, headers=None, raw=False, query=None):
    h = dict(headers or {})
    if TOKEN and 'Authorization' not in h:
        h['Authorization'] = 'Bearer ' + TOKEN
    url = '/api/mobile/v1' + path
    kw = {'headers': h}
    if query:
        kw['query_string'] = query
    if json_body is not None:
        kw['json'] = json_body
    elif data is not None:
        kw['data'] = data
    resp = getattr(client, method.lower())(url, **kw)
    if raw:
        return resp
    try:
        payload = resp.get_json()
    except Exception:
        payload = None
    if payload is None:
        payload = {'_non_json': resp.data[:200], '_status': resp.status_code}
    payload['_status'] = resp.status_code
    return payload


def section(title):
    print('\n=== ' + title + ' ===')


try:
    # ------------------------------------------------------------------ health
    section('Health')
    r = api('GET', '/health')
    check('health ok', r.get('ok') is True and r['data']['db_ok'] is True, r)
    check('health web_version', bool(r['data'].get('web_version')), r)

    # ------------------------------------------------------------------ auth
    section('Auth')
    r = api('GET', '/dashboard')
    check('bez tokenu → 401 JSON', r['_status'] == 401 and r.get('ok') is False and r.get('code') == 'unauthorized', r)

    r = api('POST', '/auth/login', {'email': 'admin', 'password': 'spatne'})
    check('špatné heslo → 401', r['_status'] == 401 and r.get('code') == 'bad_credentials', r)

    r = api('POST', '/auth/login', {'email': 'admin', 'password': 'admin', 'device_name': 'Test'})
    check('login → challenge_token', r.get('ok') and r['data'].get('challenge_token'), r)
    check('login → OTP odeslán e-mailem', otp_from_mail() is not None, SENT[-1:] )
    check('login → maskovaný e-mail', '…' in r['data'].get('otp_sent_to', ''), r['data'])
    ch = r['data']['challenge_token']

    r = api('POST', '/auth/verify', {'challenge_token': ch, 'code': '000000'})
    check('špatný kód → 401 bad_code', r['_status'] == 401 and r.get('code') == 'bad_code', r)

    r = api('POST', '/auth/verify', {'challenge_token': ch, 'code': otp_from_mail(), 'device_name': 'Pixel test', 'platform': 'android', 'app_version': '2.0.0'})
    check('verify → token', r.get('ok') and r['data'].get('token'), r)
    TOKEN = r['data']['token']
    check('verify → admin', r['data']['admin']['email'] == 'admin', r['data'].get('admin'))

    r = api('POST', '/auth/verify', {'challenge_token': ch, 'code': otp_from_mail()})
    check('opakované použití kódu odmítnuto', r['_status'] == 401, r)

    r = api('GET', '/auth/me')
    check('auth/me', r.get('ok') and r['data']['admin']['id'] == 3 and r['data']['device']['device_name'] == 'Pixel test', r)

    r = api('GET', '/auth/devices')
    check('auth/devices obsahuje aktuální', r.get('ok') and any(d['is_current'] for d in r['data']), r)

    # Druhé zařízení a odvolání
    r2 = api('POST', '/auth/login', {'email': 'admin', 'password': 'admin'})
    r2 = api('POST', '/auth/verify', {'challenge_token': r2['data']['challenge_token'], 'code': otp_from_mail(), 'device_name': 'Druhý telefon'})
    token2 = r2['data']['token']
    dev2 = r2['data']['device']['id']
    r = api('POST', '/auth/devices/revoke', {'device_id': dev2})
    check('revoke druhého zařízení', r.get('ok'), r)
    r = api('GET', '/auth/me', headers={'Authorization': 'Bearer ' + token2})
    check('odvolaný token → 401 revoked', r['_status'] == 401 and r.get('code') == 'revoked', r)

    # ------------------------------------------------------------------ dashboard
    section('Dashboard')
    r = api('GET', '/dashboard')
    d = r.get('data') or {}
    check('dashboard ok', r.get('ok') and 'stats' in d and 'kpis' in d and 'activity_30' in d and 'by_tier' in d, list(d.keys()))
    check('dashboard agent verze', d.get('agent', {}).get('agent_build_id'), d.get('agent'))
    r = api('GET', '/stats/activity')
    check('stats/activity', r.get('ok') and isinstance(r['data'], list), r)
    r = api('GET', '/stats/ranking', query={'limit': 5})
    check('stats/ranking', r.get('ok') and isinstance(r['data'], list), r)
    r = api('POST', '/agent-version', {'agent_build_id': '58', 'agent_version_display': 'v26.09.001'})
    check('agent-version set', r.get('ok'), r)
    r = api('GET', '/agent-version')
    check('agent-version get', r['data']['agent_build_id'] == '58', r)
    r = api('POST', '/agent-version', {'agent_build_id': 'x', 'agent_version_display': 'v1'})
    check('agent-version validace', r['_status'] == 400 and r.get('ok') is False, r)

    # ------------------------------------------------------------------ tiers
    section('Tarify')
    r = api('GET', '/tiers')
    check('tiers list', r.get('ok') and len(r['data']) >= 5, r)
    tiers = {t['name']: t for t in r['data']}
    r = api('POST', '/tiers/add', {'name': 'MobilTest', 'max_files_limit': 25, 'max_devices': 2, 'allow_signatures': True, 'allow_excel_export': True, 'checkout_features': 'A\nB'})
    check('tiers add', r.get('ok') and r['data'].get('tier_id'), r)
    new_tier_id = r['data']['tier_id']
    r = api('POST', '/tiers/%d/update' % new_tier_id, {'name': 'MobilTest2', 'max_files_limit': 30, 'max_devices': 3, 'allow_signatures': True, 'allow_timestamp': True, 'allow_excel_export': False, 'allow_advanced_filters': False})
    check('tiers update', r.get('ok'), r)
    r = api('GET', '/tiers')
    t2 = [t for t in r['data'] if t['id'] == new_tier_id][0]
    check('tiers update uloženo', t2['name'] == 'MobilTest2' and int(t2['max_files_limit']) == 30 and int(t2['max_devices']) == 3, t2)

    # ------------------------------------------------------------------ licenses
    section('Licence')
    pro_id = tiers['Pro']['id']
    basic_id = tiers['Basic']['id']
    r = api('POST', '/licenses/create', {'user_name': 'Ing. Jana Nováková', 'email': 'novakova@test.cz', 'tier_id': pro_id, 'password': 'tajne123', 'days': 365})
    check('license create', r.get('ok') and r['data'].get('api_key'), r)
    key1 = r['data']['api_key']
    r = api('POST', '/licenses/create', {'user_name': 'Dup', 'email': 'novakova@test.cz', 'tier_id': pro_id})
    check('license create duplicitní e-mail → 400', r['_status'] == 400 and r.get('ok') is False, r)
    r = api('POST', '/licenses/create', {'user_name': 'Projekce Dvořák', 'email': 'dvorak@test.cz', 'tier_id': basic_id, 'days': 20})
    key2 = r['data']['api_key']
    r = api('POST', '/licenses/create', {'user_name': '', 'email': ''})
    check('license create validace', r['_status'] == 400, r)

    r = api('GET', '/licenses')
    check('licenses list', r.get('ok') and len(r['data']['licenses']) >= 3 and 'revenue_summary' in r['data'] and 'product_tiers' in r['data'], r.get('data', {}).keys())
    lic1 = [l for l in r['data']['licenses'] if l['api_key'] == key1][0]
    check('licenses list price_label', lic1['price_label'].endswith('Kč'), lic1['price_label'])
    r = api('GET', '/licenses', query={'q': 'dvorak'})
    check('licenses filtr q', len(r['data']['licenses']) == 1 and r['data']['licenses'][0]['api_key'] == key2, r['data']['licenses'])
    r = api('GET', '/licenses', query={'tier': 'Pro'})
    check('licenses filtr tier', all(l['tier_name'] == 'Pro' for l in r['data']['licenses']) and len(r['data']['licenses']) >= 1, r['data']['licenses'])
    r = api('GET', '/licenses', query={'status': 'expiring'})
    check('licenses filtr expiring (20 dní)', any(l['api_key'] == key2 for l in r['data']['licenses']), [l['email'] for l in r['data']['licenses']])

    r = api('GET', '/licenses/' + key1)
    check('license detail', r.get('ok') and r['data']['license']['email'] == 'novakova@test.cz' and 'devices' in r['data'] and 'billing' in r['data'], r)
    check('license detail password_plain', r['data']['license'].get('password_plain') == 'tajne123', r['data']['license'].get('password_plain'))
    check('license detail bez hashe', 'password_hash' not in r['data']['license'], list(r['data']['license'].keys()))
    r = api('GET', '/licenses/neexistuje')
    check('license detail 404', r['_status'] == 404, r)

    r = api('POST', '/licenses/%s/update' % key1, {'user_name': 'Ing. Jana Nováková, PhD.', 'license_expires': '2027-06-30', 'payment_method': 'Převod', 'last_payment_date': '2026-09-01', 'is_test': False, 'max_devices': 2})
    check('license update', r.get('ok'), r)
    r = api('GET', '/licenses/' + key1)
    l = r['data']['license']
    check('license update uloženo', l['user_name'].endswith('PhD.') and str(l['license_expires']).startswith('2027-06-30') and l['payment_method'] == 'Převod', l)
    check('license update zachoval tarif', l['tier_name'] == 'Pro', l['tier_name'])

    r = api('POST', '/licenses/%s/set-tier' % key1, {'tier_id': basic_id})
    check('license set-tier', r.get('ok'), r)
    r = api('GET', '/licenses/' + key1)
    check('license set-tier uloženo', r['data']['license']['tier_name'] == 'Basic', r['data']['license']['tier_name'])

    r = api('POST', '/licenses/%s/extend' % key1, {'days': 365})
    check('license extend', r.get('ok') and r['data']['license_expires'] == '2028-06-29', r)
    r = api('POST', '/licenses/%s/extend' % key1, {'days': 0})
    check('license extend validace', r['_status'] == 400, r)

    r = api('POST', '/licenses/%s/toggle' % key1, {'is_active': False})
    check('license toggle off', r.get('ok'), r)
    r = api('GET', '/licenses', query={'status': 'blocked'})
    check('license blokovaná ve filtru', any(l['api_key'] == key1 for l in r['data']['licenses']), r['data']['licenses'])
    r = api('POST', '/licenses/%s/toggle' % key1, {'is_active': True})
    check('license toggle on', r.get('ok'), r)

    r = api('POST', '/licenses/%s/set-test' % key1, {'is_test': True})
    check('license set-test', r.get('ok') and r['data']['is_test'] is True, r)
    r = api('POST', '/licenses/%s/set-test' % key1, {'is_test': False})

    r = api('POST', '/licenses/%s/set-password' % key1, {'new_password': 'abc'})
    check('license set-password krátké → 400', r['_status'] == 400, r)
    r = api('POST', '/licenses/%s/set-password' % key1, {'new_password': 'noveheslo1'})
    check('license set-password', r.get('ok'), r)
    r = api('GET', '/licenses/' + key1)
    check('license set-password uloženo', r['data']['license'].get('password_plain') == 'noveheslo1', r['data']['license'].get('password_plain'))

    r = api('GET', '/licenses/%s/welcome-package' % key1)
    check('welcome package', r.get('ok') and 'API klíč: ' + key1 in r['data']['email_body'] and 'noveheslo1' in r['data']['email_body'], r)

    # Zařízení
    db = admin_routes.get_db()
    conn = db.get_connection(); conn.execute("INSERT INTO user_devices (user_id, machine_id, machine_name, last_seen, is_blocked, created_at) VALUES (?, 'MACH-1', 'NB-NOVAKOVA', datetime('now'), 0, datetime('now'))", (key1,)); conn.commit(); conn.close()
    r = api('GET', '/licenses/%s/devices' % key1)
    check('devices list', r.get('ok') and len(r['data']['devices']) == 1 and r['data']['active_count'] == 1, r)
    r = api('POST', '/licenses/%s/devices/block' % key1, {'machine_id': 'MACH-1'})
    check('device block', r.get('ok'), r)
    r = api('GET', '/licenses/%s/devices' % key1)
    check('device blocked flag', r['data']['devices'][0]['is_blocked'] == 1, r['data']['devices'])
    r = api('POST', '/licenses/%s/devices/unblock' % key1, {'machine_id': 'MACH-1'})
    check('device unblock', r.get('ok'), r)
    r = api('POST', '/licenses/%s/devices/remove' % key1, {'machine_id': 'NEEXISTUJE'})
    check('device remove 404', r['_status'] == 404, r)
    r = api('POST', '/licenses/%s/devices/remove' % key1, {'machine_id': 'MACH-1'})
    check('device remove', r.get('ok'), r)
    r = api('POST', '/licenses/%s/reset-devices' % key1)
    check('reset devices', r.get('ok') and 'deleted' in r['data'], r)

    # Fakturace
    r = api('POST', '/licenses/%s/billing' % key1, {'description': 'Licence Pro 2026', 'amount_czk': '1590', 'paid_at': '2026-09-02', 'period_year': 2026, 'invoice_kind': 'initial'})
    check('billing add', r.get('ok'), r)
    r = api('GET', '/licenses/%s/billing' % key1)
    check('billing list', r.get('ok') and len(r['data']['data']) == 1 and r['data']['data'][0]['amount_czk'] == 1590, r)
    r = api('GET', '/licenses/%s/audit' % key1)
    check('audit', r.get('ok') and 'logs' in r['data'], r)

    # ------------------------------------------------------------------ orders
    section('Objednávky')
    conn = db.get_connection()
    conn.execute("INSERT INTO pending_orders (jmeno_firma, ico, email, tarif, status, created_at, order_display_number, amount_czk, ulice, mesto, psc) VALUES ('Stavoprojekt s.r.o.', '12345678', 'stavo@test.cz', 'pro', 'NEW_ORDER', datetime('now'), '2026-101', 1590, 'Dlouhá 1', 'Ostrava', '70200')")
    conn.execute("INSERT INTO pending_orders (jmeno_firma, ico, email, tarif, status, created_at, order_display_number, amount_czk) VALUES ('Smazat s.r.o.', '', 'del@test.cz', 'basic', 'NEW_ORDER', datetime('now'), '2026-102', 1090)")
    conn.execute("INSERT INTO pending_orders (jmeno_firma, ico, email, tarif, status, created_at, order_display_number, amount_czk) VALUES ('Smazat2 s.r.o.', '', 'del2@test.cz', 'basic', 'NEW_ORDER', datetime('now'), '2026-103', 1090)")
    conn.commit(); conn.close()
    r = api('GET', '/orders')
    check('orders list', r.get('ok') and len(r['data']['orders']) == 3 and r['data']['counts']['pending'] == 3, r.get('data', {}).get('counts'))
    order = [o for o in r['data']['orders'] if o['email'] == 'stavo@test.cz'][0]
    oid = order['id']
    check('orders enrich', order['tarif_label'] == 'Pro' and order['status_label'] == 'Objednáno' and order['has_active_license'] is False, order)
    r = api('GET', '/orders/%d' % oid)
    check('order detail', r.get('ok') and r['data']['id'] == oid, r)
    r = api('POST', '/orders/%d/edit' % oid, {'jmeno_firma': 'Stavoprojekt Ostrava s.r.o.', 'amount_czk_final': '1490'})
    check('order edit', r.get('ok'), r)
    r = api('GET', '/orders/%d' % oid)
    check('order edit uloženo (ostatní pole zachována)', r['data']['jmeno_firma'] == 'Stavoprojekt Ostrava s.r.o.' and r['data']['amount_czk_final'] == 1490 and r['data']['ico'] == '12345678', r['data'])

    r = api('POST', '/orders/%d/generate-invoice' % oid)
    check('generate invoice', r.get('ok'), r)
    r = api('GET', '/orders/%d' % oid)
    check('generate invoice → WAITING + has_invoice', r['data']['status'] == 'WAITING_PAYMENT' and r['data']['has_invoice'] is True, r['data'])
    resp = api('GET', '/orders/%d/invoice.pdf' % oid, raw=True)
    check('invoice pdf download', resp.status_code == 200 and resp.data[:4] == b'%PDF', (resp.status_code, resp.data[:20]))
    r = api('POST', '/orders/%d/regenerate-invoice' % oid)
    check('regenerate invoice', r.get('ok'), r)

    n_before = len(SENT)
    r = api('GET', '/orders/email-preview', query={'type': 'payment', 'order_id': oid})
    check('email preview payment', r.get('ok') and r['data'].get('subject') and r['data']['recipient'] == 'stavo@test.cz' and r['data']['has_invoice'] is True, r)
    r = api('POST', '/orders/email-send', {'recipient': 'stavo@test.cz', 'subject': r['data']['subject'], 'body': r['data']['body_plain'], 'action_type': 'payment', 'order_id': oid, 'attach_invoice': True})
    check('email send payment', r.get('ok') and len(SENT) == n_before + 1 and SENT[-1].get('attachment'), r)
    r = api('GET', '/orders/%d' % oid)
    check('email send → payment_sent', r['data']['status'] == 'payment_sent' and r['data']['is_waiting'], r['data']['status'])

    r = api('POST', '/orders/%d/send-payment' % oid)
    check('send-payment (rychlé)', r.get('ok') and len(SENT) == n_before + 2, r)

    r = api('POST', '/orders/%d/apply-discount' % oid)
    check('apply discount', r.get('ok'), r)
    r = api('GET', '/orders/%d' % oid)
    check('apply discount uloženo', r['data']['discount_applied'] and r['data']['amount_czk_final'] < 1590, r['data'])

    # Stav payment_sent → jako na webu: „Zaplaceno a poslat aktivaci“ = email-preview activation (vytvoří licenci)
    r = api('POST', '/orders/%d/confirm-payment' % oid)
    check('confirm payment u payment_sent → chyba (jako web)', r['_status'] == 400 and r.get('ok') is False, r)
    r = api('GET', '/orders/email-preview', query={'type': 'activation', 'order_id': oid})
    check('email preview activation (vytvoří licenci)', r.get('ok') and r['data'].get('api_key') and r['data'].get('set_password_url') and r['data']['recipient'] == 'stavo@test.cz', r)
    api_key_order = r['data']['api_key']
    r = api('POST', '/orders/email-send', {'recipient': 'stavo@test.cz', 'subject': r['data']['subject'], 'body': r['data']['body_html'], 'action_type': 'activation', 'order_id': oid, 'api_key': api_key_order})
    check('email send activation', r.get('ok'), r)
    r = api('GET', '/orders/%d' % oid)
    check('aktivace → ACTIVE + has_active_license', r['data']['status'] == 'ACTIVE' and r['data']['has_active_license'] is True and r['data']['api_key'] == api_key_order, r['data'])

    # Nová objednávka NEW_ORDER → confirm-payment (legacy tlačítko POTVRDIT PLATBU)
    conn = db.get_connection()
    conn.execute("INSERT INTO pending_orders (jmeno_firma, ico, email, tarif, status, created_at, order_display_number, amount_czk) VALUES ('Potvrdit s.r.o.', '', 'potvrdit@test.cz', 'basic', 'NEW_ORDER', datetime('now'), '2026-104', 1090)")
    conn.commit(); conn.close()
    oid2 = [o for o in api('GET', '/orders')['data']['orders'] if o['email'] == 'potvrdit@test.cz'][0]['id']
    r = api('POST', '/orders/%d/confirm-payment' % oid2)
    check('confirm payment (NEW_ORDER)', r.get('ok') and r.get('data', {}).get('api_key'), r)
    r = api('GET', '/orders/%d' % oid2)
    check('confirm payment → ACTIVE', r['data']['status'] == 'ACTIVE' and r['data']['has_active_license'] is True, r['data'])
    r = api('POST', '/orders/%d/confirm-payment' % oid2)
    check('confirm payment podruhé → chyba', r['_status'] == 400 and r.get('ok') is False, r)
    r = api('POST', '/orders/%d/delete' % oid2)
    check('delete potvrzené objednávky', r.get('ok'), r)

    r = api('POST', '/orders/%d/delete-user' % oid)
    check('delete user from order', r.get('ok'), r)
    r = api('GET', '/orders/%d' % oid)
    check('delete user → WAITING_PAYMENT', r['data']['status'] == 'WAITING_PAYMENT' and r['data']['has_active_license'] is False, r['data'])
    r = api('POST', '/orders/%d/activate-without-invoice' % oid)
    check('activate without invoice', r.get('ok') and r['data'].get('api_key'), r)

    ids = [o['id'] for o in api('GET', '/orders')['data']['orders'] if o['email'].startswith('del')]
    r = api('POST', '/orders/bulk-send-payment', {'order_ids': ids})
    check('bulk send payment', r.get('ok'), r)
    r = api('POST', '/orders/bulk-delete', {'order_ids': ids})
    check('bulk delete', r.get('ok'), r)
    check('bulk delete → zbývá 1', len(api('GET', '/orders')['data']['orders']) == 1, [o['email'] for o in api('GET', '/orders')['data']['orders']])
    r = api('POST', '/orders/9999/delete')
    check('delete neexistující → chyba', r.get('ok') is False, r)

    r = api('POST', '/orders/auto-activate-csob', {'value': True})
    check('auto activate set', r.get('ok'), r)
    r = api('GET', '/orders/auto-activate-csob')
    check('auto activate get', r['data']['auto_activate_csob'] is True, r)
    api('POST', '/orders/auto-activate-csob', {'value': False})

    # ------------------------------------------------------------------ csob
    section('ČSOB')
    r = api('POST', '/csob/manual', {'variabilni_symbol': '2026101', 'castka_czk': '1234,50', 'protiucet': '123/0300', 'datum_zauctovani': '2026-09-02'})
    check('csob manual', r.get('ok'), r)
    r = api('GET', '/csob')
    check('csob list', r.get('ok') and len(r['data']['platby']) == 1 and r['data']['platby'][0]['castka_czk'] == 1234.5 and 'imap_status' in r['data'], r)
    pid = r['data']['platby'][0]['id']
    r = api('POST', '/csob/%d/vyridit' % pid)
    check('csob vyridit', r.get('ok'), r)
    r = api('GET', '/csob', query={'stav': 'vyrizeno'})
    check('csob filtr stav', len(r['data']['platby']) == 1 and r['data']['platby'][0]['stav_label'] == 'Vyřízeno', r['data']['platby'])
    r = api('POST', '/csob/manual', {'variabilni_symbol': '1', 'castka_czk': 'xx'})
    check('csob manual validace', r.get('ok') is False, r)
    r = api('POST', '/csob/upload-eml', data={'eml_file': (io.BytesIO(b'From: test@example.com\r\nSubject: x\r\n\r\nnic'), 'test.eml'), 'skip_dkim': '1'})
    check('csob upload eml (odpověď JSON)', '_non_json' not in r and r['_status'] in (200, 400), r)

    # ------------------------------------------------------------------ finance
    section('Finance')
    r = api('GET', '/finance')
    check('finance', r.get('ok') and 'summary' in r['data'] and 'invoices' in r['data'] and 'monthly_revenue' in r['data'], r)
    resp = api('GET', '/finance/invoices.zip', raw=True)
    check('finance zip (ZIP nebo 404 JSON)', (resp.status_code == 200 and resp.data[:2] == b'PK') or (resp.status_code == 404 and resp.is_json), resp.status_code)

    # ------------------------------------------------------------------ trial / IP
    section('Trial a IP')
    r = api('GET', '/trial')
    check('trial get', r.get('ok') and 'web_trial_files_limit' in r['data'], r)
    r = api('POST', '/trial/limit', {'limit': 6})
    check('trial limit', r.get('ok'), r)
    check('trial limit uloženo', api('GET', '/trial')['data']['web_trial_files_limit'] == 6, None)
    r = api('POST', '/trial/reset', {'machine_id': 'NEEXISTUJE'})
    check('trial reset neexistující → 404', r['_status'] == 404, r)
    r = api('POST', '/web-trial/reset', {'ip_address': '10.0.0.1'})
    check('web-trial reset', r.get('ok'), r)
    r = api('POST', '/ip-block', {'ip_address': '10.0.0.9', 'action': 'block', 'hours': 5})
    check('ip block', r.get('ok'), r)
    r = api('GET', '/web-checks/ip', query={'ip': '10.0.0.9'})
    check('web-checks ip detail blokace', r.get('ok') and r['data']['block'] and r['data']['block'].get('blocked_until'), r)
    r = api('POST', '/ip-block', {'ip_address': '10.0.0.9', 'action': 'unblock'})
    check('ip unblock', r.get('ok'), r)
    r = api('POST', '/web-check/reset', {'ip_address': '10.0.0.9'})
    check('web-check reset', r.get('ok'), r)
    r = api('GET', '/web-checks')
    check('web-checks list', r.get('ok') and 'rows' in r['data'] and 'stats' in r['data'], r)
    r = api('POST', '/web-checks/limit', {'limit': 4})
    check('web-checks limit', r.get('ok'), r)
    r = api('GET', '/free-check-usage', query={'hours': 12})
    check('free-check-usage', r.get('ok') and r['data']['hours'] == 12, r)

    # ------------------------------------------------------------------ logs / analytics
    section('Logy a návštěvnost')
    for cat in ('activity', 'system', 'user', 'payment'):
        r = api('GET', '/logs', query={'category': cat})
        check('logs ' + cat, r.get('ok') and isinstance(r['data']['logs'], list), r)
    r = api('GET', '/logs', query={'category': 'payment', 'user_id': key1})
    check('logs payment filtr user', r.get('ok') and any('fakturace' in (l.get('action') or '') for l in r['data']['logs']), r['data']['logs'][:3])
    r = api('GET', '/analytics', query={'days': 7})
    check('analytics', r.get('ok') and r['data']['days'] == 7 and 'daily' in r['data'], r)

    # ------------------------------------------------------------------ content
    section('Obsah')
    r = api('GET', '/content/faq')
    n_faq = len(r['data'])
    r = api('POST', '/content/faq/add', {'question': 'Mobilní otázka?', 'answer': 'Odpověď.', 'order_index': 99})
    check('faq add', r.get('ok'), r)
    r = api('GET', '/content/faq')
    check('faq add uloženo', len(r['data']) == n_faq + 1, len(r['data']))
    fid = [f for f in r['data'] if f['question'] == 'Mobilní otázka?'][0]['id']
    r = api('POST', '/content/faq/%d/update' % fid, {'question': 'Mobilní otázka 2?', 'answer': 'Odpověď 2.'})
    check('faq update', r.get('ok'), r)
    r = api('POST', '/content/faq/add', {'question': '', 'answer': 'x'})
    check('faq add validace', r.get('ok') is False, r)
    r = api('POST', '/content/faq/%d/delete' % fid)
    check('faq delete', r.get('ok'), r)

    r = api('GET', '/content/updates')
    check('updates get', r.get('ok') and isinstance(r['data']['landing_updates'], list), r)
    n_upd = len(r['data']['landing_updates'])
    r = api('POST', '/content/updates', {'action': 'add_entry', 'month': '09/2026', 'title': 'Mobilní admin', 'items': ['Nová aplikace', 'API']})
    check('updates add_entry', r.get('ok'), r)
    r = api('GET', '/content/updates')
    check('updates add uloženo', len(r['data']['landing_updates']) == n_upd + 1 and r['data']['landing_updates'][0]['title'] == 'Mobilní admin', r['data']['landing_updates'][:1])
    r = api('POST', '/content/updates', {'action': 'delete_entry', 'index': 0})
    check('updates delete_entry', r.get('ok'), r)
    r = api('POST', '/content/updates', {'action': 'save_download_whats_new', 'download_whats_new': 'Text X'})
    check('updates whats new', r.get('ok') and api('GET', '/content/updates')['data']['download_whats_new'] == 'Text X', r)

    r = api('GET', '/content/coming-soon')
    check('coming-soon get', r.get('ok') and isinstance(r['data']['cards'], list), r)
    cards = r['data']['cards']
    cards[0]['title'] = 'Path Checker M'
    r = api('POST', '/content/coming-soon', {'cards': cards, 'intro': 'Úvod M'})
    check('coming-soon save', r.get('ok'), r)
    r = api('GET', '/content/coming-soon')
    check('coming-soon uloženo', r['data']['cards'][0]['title'] == 'Path Checker M' and r['data']['intro'] == 'Úvod M', r['data'])

    r = api('GET', '/content/marketing-emails')
    check('marketing get', r.get('ok') and 'order_confirmation_subject' in r['data'], r)
    tpl = dict(r['data'])
    tpl['footer_text'] = 'Patička M'
    r = api('POST', '/content/marketing-emails', tpl)
    check('marketing save', r.get('ok'), r)
    check('marketing uloženo', api('GET', '/content/marketing-emails')['data'].get('footer_text') == 'Patička M', None)
    r = api('POST', '/content/marketing-emails/test', {'to': 'test@test.cz'})
    check('marketing test mail', r.get('ok') and SENT[-1]['to'] == 'test@test.cz', r)

    r = api('GET', '/content/checkout-texts')
    check('checkout-texts get', r.get('ok') and 'checkout_page_title' in r['data']['texts'], r)
    r = api('POST', '/content/checkout-texts', {'checkout_page_title': 'Objednávka M'})
    check('checkout-texts save', r.get('ok'), r)
    check('checkout-texts uloženo', api('GET', '/content/checkout-texts')['data']['texts']['checkout_page_title'] == 'Objednávka M', None)

    r = api('GET', '/content/company')
    check('company get', r.get('ok') and r['data']['provider_ico'], r)
    r = api('POST', '/content/company', {'provider_phone': '+420 777 000 000'})
    check('company save', r.get('ok'), r)
    c = api('GET', '/content/company')['data']
    check('company uloženo + zachováno', c['provider_phone'] == '+420 777 000 000' and c['provider_ico'] == '04830661', c)

    r = api('POST', '/content/help', {'info_card_content': '<p>Info M</p>'})
    check('help save', r.get('ok') and api('GET', '/content/help')['data']['info_card_content'] == '<p>Info M</p>', r)

    # ------------------------------------------------------------------ settings
    section('Nastavení')
    r = api('GET', '/settings')
    check('settings get', r.get('ok') and 'actions' in r['data'] and 'env_labels' in r['data'] and 'pricing_tarifs' in r['data'], list((r.get('data') or {}).keys())[:5])
    r = api('POST', '/settings/save_contact', {'contact_email': 'm@test.cz', 'contact_phone': '123'})
    check('settings save_contact', r.get('ok'), r)
    check('settings save_contact uloženo', api('GET', '/settings')['data']['contact_email'] == 'm@test.cz', None)
    r = api('POST', '/settings/global', {'maintenance_mode': False})
    check('settings global', r.get('ok') and api('GET', '/settings')['data']['allow_new_registrations'] in (True, 1), r)
    r = api('POST', '/settings/save_sales', {'price_basic': 1190})
    check('settings save_sales', r.get('ok') and api('GET', '/settings')['data']['price_basic'] == 1190, r)
    r = api('POST', '/settings/save_pricing', {'pricing_tarifs_json': '{nevalidni'})
    check('settings JSON validace', r['_status'] == 400, r)
    r = api('POST', '/settings/save_environment', {'order_number_next': '250', 'label_status_new': 'Nová M'})
    check('settings save_environment', r.get('ok') and api('GET', '/settings')['data']['env_labels']['order_number_next'] == '250', r)
    r = api('POST', '/settings/save_mail', {'mail_port': '587', 'mail_server': 'smtp.test.cz'})
    check('settings save_mail', r.get('ok') and api('GET', '/settings')['data']['mail_port'] == '587', r)
    r = api('POST', '/settings/neznama', {})
    check('settings neznámá záložka → 404', r['_status'] == 404, r)

    # ------------------------------------------------------------------ account
    section('Účet')
    r = api('POST', '/account/change-password', {'current_password': 'spatne', 'new_password': 'novyadmin1'})
    check('change password špatné aktuální → chyba', r.get('ok') is False, r)
    r = api('POST', '/account/change-password', {'current_password': 'admin', 'new_password': 'novyadmin1'})
    check('change password', r.get('ok'), r)
    r = api('POST', '/auth/login', {'email': 'admin', 'password': 'novyadmin1'})
    check('login novým heslem', r.get('ok'), r)

    # ------------------------------------------------------------------ license delete + logout
    section('Úklid')
    r = api('POST', '/licenses/%s/delete' % key2)
    check('license delete', r.get('ok'), r)
    r = api('GET', '/licenses/' + key2)
    check('license delete → 404', r['_status'] == 404, r)
    r = api('POST', '/auth/logout')
    check('logout', r.get('ok'), r)
    r = api('GET', '/auth/me')
    check('po logoutu 401', r['_status'] == 401, r)

    # Web admin nesmí být dotčen: /login HTML stále funguje a /admin bez session přesměruje
    resp = client.get('/login')
    check('web /login stále HTML 200', resp.status_code == 200 and b'csrf_token' in resp.data, resp.status_code)
    resp = client.get('/admin')
    check('web /admin bez session → redirect', resp.status_code in (301, 302, 308), resp.status_code)

except Exception:
    traceback.print_exc()
    FAILED.append(('VÝJIMKA', traceback.format_exc()[-800:]))

print('\n==========================================')
print('Prošlo: %d   Selhalo: %d' % (len(PASSED), len(FAILED)))
for name, detail in FAILED:
    print('  FAIL:', name, '|', str(detail)[:400])
shutil.rmtree(_tmpdir, ignore_errors=True)
sys.exit(1 if FAILED else 0)
