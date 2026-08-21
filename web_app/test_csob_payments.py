#!/usr/bin/env python3
# test_csob_payments.py – povinné scénáře párování ČSOB avíz
#
# Spuštění z web_app:
#   python test_csob_payments.py
#
# Používá dočasnou SQLite DB a fixture tests/fixtures/csob_avizo_s_vs.eml

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from email.message import EmailMessage
from unittest import mock

_WEB_APP = os.path.dirname(os.path.abspath(__file__))
if _WEB_APP not in sys.path:
    sys.path.insert(0, _WEB_APP)

FIXTURE = os.path.join(_WEB_APP, 'tests', 'fixtures', 'csob_avizo_s_vs.eml')


def _load_fixture() -> bytes:
    with open(FIXTURE, 'rb') as f:
        return f.read()


def _make_db():
    from database import Database
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    db = Database(path)
    db._test_db_path = path
    return db


def _cleanup_db(db):
    path = getattr(db, '_test_db_path', None)
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _seed_order(db, vs='160', amount=1590.0, status='WAITING_PAYMENT', email='zakaznik@example.cz'):
    oid = db.insert_pending_order(
        jmeno_firma='Test Firma',
        ico='12345678',
        email=email,
        tarif='pro',
        status=status,
        order_display_number=str(vs),
        amount_czk=amount,
    )
    db.update_pending_order_invoice_number(oid, str(vs))
    # zajistit amount_czk_final
    db.update_pending_order(oid, amount_czk=amount, amount_czk_final=amount)
    # status (insert může mít pending default v některých cestách)
    db.update_pending_order_status(oid, status)
    return oid


def _ensure_pro_tier(db):
    tiers = db.get_all_license_tiers() or []
    for t in tiers:
        if (t.get('name') or '').lower() == 'pro':
            return t
    if hasattr(db, 'insert_tier'):
        tid, err = db.insert_tier('Pro', max_files_limit=100, allow_signatures=True,
                                  allow_timestamp=True, allow_excel_export=True, max_devices=2)
        if tid:
            return db.get_tier_by_id(tid)
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute(
        '''INSERT OR IGNORE INTO license_tiers
           (name, max_files_limit, allow_signatures, allow_timestamp, allow_excel_export, max_devices)
           VALUES ('Pro', 100, 1, 1, 1, 2)'''
    )
    conn.commit()
    conn.close()
    return db.get_tier_by_name('pro') or db.get_tier_by_name('Pro')


class TestParser(unittest.TestCase):
    def test_parse_fixture_amount_and_vs(self):
        from csob_payments import parse_csob_avizo_html, _get_html_body
        from email import message_from_bytes
        raw = _load_fixture()
        msg = message_from_bytes(raw)
        html = _get_html_body(msg)
        parsed = parse_csob_avizo_html(html)
        self.assertNotIn('error', parsed)
        self.assertEqual(parsed['castka_haleru'], 159000)
        self.assertEqual(parsed['mena'], 'CZK')
        self.assertEqual(parsed['variabilni_symbol'], '160')
        self.assertEqual(parsed['protiucet'], '107496683/0100')
        self.assertEqual(parsed['datum_zauctovani'], '12.8.2026')
        # Nesmí vzít zůstatek místo částky (ve fixture stejné číslo – ověříme že pole Částka existuje)
        self.assertIn('Částka', parsed.get('fields') or {})

    def test_parse_amount_nbsp(self):
        from csob_payments import parse_amount_to_haleru
        r = parse_amount_to_haleru('+1\xa0590,00 CZK')
        self.assertEqual(r, (159000, 'CZK'))

    def test_missing_vs_from_html(self):
        from csob_payments import parse_csob_avizo_html, _get_html_body
        from email import message_from_bytes
        raw = _load_fixture()
        msg = message_from_bytes(raw)
        html = _get_html_body(msg)
        # Odstranit řádek Variabilní symbol
        html2 = html.replace('Variabilní symbol', 'XXX_REMOVED').replace('Variabiln=C3=AD symbol', 'XXX')
        # Po dekódu je už unicode
        html2 = html.replace('Variabilní symbol', 'Odstraneno')
        parsed = parse_csob_avizo_html(html2)
        self.assertNotIn('error', parsed)
        self.assertIsNone(parsed.get('variabilni_symbol'))


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.db = _make_db()
        _ensure_pro_tier(self.db)

    def tearDown(self):
        _cleanup_db(self.db)

    def test_no_dkim_no_activation(self):
        """Zpráva bez platného DKIM → podezrele, žádná aktivace."""
        from csob_payments import process_raw_email
        oid = _seed_order(self.db, vs='160', amount=1590)
        # Fake mail bez DKIM
        msg = EmailMessage()
        msg['From'] = 'noreply@csob.cz'
        msg['Subject'] = 'Moje info - Avízo'
        msg['Message-ID'] = '<test-no-dkim@example>'
        msg.set_content('<html><body><table><tr><td>Částka</td><td>+1 590,00 CZK</td></tr>'
                        '<tr><td>Variabilní symbol</td><td>160</td></tr></table></body></html>',
                        subtype='html')
        raw = msg.as_bytes()
        with mock.patch('csob_payments.verify_dkim', return_value=(False, 'neplatny')):
            res = process_raw_email(self.db, raw, auto_activate=True)
        self.assertEqual(res.get('stav'), 'podezrele')
        order = self.db.get_pending_order_by_id(oid)
        self.assertNotEqual((order.get('status') or '').upper(), 'ACTIVE')

    def test_duplicate_one_activation(self):
        from csob_payments import process_raw_email
        _seed_order(self.db, vs='160', amount=1590)
        raw = _load_fixture()
        with mock.patch('csob_payments.verify_dkim', return_value=(True, 'OK')):
            with mock.patch('csob_payments.send_activation_for_order', return_value=True) as send_mock:
                r1 = process_raw_email(self.db, raw, auto_activate=True)
                r2 = process_raw_email(self.db, raw, auto_activate=True)
        self.assertTrue(r1.get('activated') or r1.get('stav') == 'sparovano')
        self.assertTrue(r2.get('duplicate'))
        self.assertEqual(send_mock.call_count, 1)
        platby = self.db.list_csob_platby()
        self.assertEqual(len(platby), 1)

    def test_amount_one_crown_less(self):
        from csob_payments import process_raw_email
        oid = _seed_order(self.db, vs='160', amount=1591)  # objednávka o 1 Kč víc
        raw = _load_fixture()
        with mock.patch('csob_payments.verify_dkim', return_value=(True, 'OK')):
            with mock.patch('csob_payments.send_activation_for_order') as send_mock:
                res = process_raw_email(self.db, raw, auto_activate=True)
        self.assertEqual(res.get('stav'), 'nesparovano')
        self.assertEqual(res.get('reason'), 'amount_mismatch')
        send_mock.assert_not_called()
        order = self.db.get_pending_order_by_id(oid)
        self.assertNotEqual((order.get('status') or '').upper(), 'ACTIVE')

    def test_missing_vs_nesparovano(self):
        from csob_payments import process_raw_email, parse_csob_avizo_html, _get_html_body
        from email import message_from_bytes
        _seed_order(self.db, vs='160', amount=1590)
        raw = _load_fixture()
        msg = message_from_bytes(raw)
        html = _get_html_body(msg).replace('Variabilní symbol', 'Odstraneno')
        # Sestav nový mail s upraveným HTML
        msg2 = EmailMessage()
        msg2['From'] = 'noreply@csob.cz'
        msg2['Subject'] = 'Moje info - Avízo'
        msg2['Message-ID'] = '<test-no-vs@csob.cz>'
        msg2.set_content(html, subtype='html')
        with mock.patch('csob_payments.verify_dkim', return_value=(True, 'OK')):
            with mock.patch('csob_payments.send_activation_for_order') as send_mock:
                res = process_raw_email(self.db, msg2.as_bytes(), auto_activate=True)
        self.assertEqual(res.get('stav'), 'nesparovano')
        self.assertEqual(res.get('reason'), 'missing_vs')
        send_mock.assert_not_called()

    def test_unknown_vs(self):
        from csob_payments import process_raw_email
        _seed_order(self.db, vs='999999', amount=1590)
        raw = _load_fixture()  # VS 160
        with mock.patch('csob_payments.verify_dkim', return_value=(True, 'OK')):
            with mock.patch('csob_payments.send_activation_for_order') as send_mock:
                res = process_raw_email(self.db, raw, auto_activate=True)
        self.assertEqual(res.get('stav'), 'nesparovano')
        self.assertEqual(res.get('reason'), 'unknown_vs')
        send_mock.assert_not_called()

    def test_unparseable_mail(self):
        from csob_payments import process_raw_email
        msg = EmailMessage()
        msg['From'] = 'noreply@csob.cz'
        msg['Subject'] = 'Moje info - Avízo'
        msg['Message-ID'] = '<test-bad@csob.cz>'
        msg.set_content('<html><body>Ahoj, nic tu není</body></html>', subtype='html')
        with mock.patch('csob_payments.verify_dkim', return_value=(True, 'OK')):
            res = process_raw_email(self.db, msg.as_bytes(), auto_activate=True)
        self.assertEqual(res.get('stav'), 'chyba_parsovani')
        platba = self.db.get_csob_platba_by_id(res.get('platba_id'))
        self.assertIsNotNone(platba)
        self.assertTrue(platba.get('raw_email'))

    def test_overpayment_on_active(self):
        from csob_payments import process_raw_email
        oid = _seed_order(self.db, vs='160', amount=1590, status='ACTIVE')
        raw = _load_fixture()
        with mock.patch('csob_payments.verify_dkim', return_value=(True, 'OK')):
            with mock.patch('csob_payments.send_activation_for_order') as send_mock:
                res = process_raw_email(self.db, raw, auto_activate=True)
        self.assertEqual(res.get('stav'), 'preplatek')
        send_mock.assert_not_called()

    def test_match_but_autoactivate_off(self):
        from csob_payments import process_raw_email
        oid = _seed_order(self.db, vs='160', amount=1590)
        self.db.set_global_setting('auto_activate_csob', '0')
        raw = _load_fixture()
        with mock.patch('csob_payments.verify_dkim', return_value=(True, 'OK')):
            with mock.patch('csob_payments.send_activation_for_order') as send_mock:
                res = process_raw_email(self.db, raw, auto_activate=False)
        self.assertEqual(res.get('stav'), 'shoda')
        self.assertFalse(res.get('activated'))
        send_mock.assert_not_called()
        order = self.db.get_pending_order_by_id(oid)
        self.assertNotEqual((order.get('status') or '').upper(), 'ACTIVE')

    def test_hash_idempotence_unique_constraint(self):
        h = 'abc' * 21 + '0'  # 64 hex-ish
        id1 = self.db.insert_csob_platba(message_hash=h, castka_haleru=100, stav='nove', dkim_ok=True)
        id2 = self.db.insert_csob_platba(message_hash=h, castka_haleru=100, stav='nove', dkim_ok=True)
        self.assertIsNotNone(id1)
        self.assertIsNone(id2)


if __name__ == '__main__':
    if not os.path.isfile(FIXTURE):
        print('FAIL: chybí fixture', FIXTURE)
        sys.exit(1)
    unittest.main(verbosity=2)
