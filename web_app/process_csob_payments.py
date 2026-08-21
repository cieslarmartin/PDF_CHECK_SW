#!/usr/bin/env python3
# process_csob_payments.py – CLI pro cron / Always-on task na PythonAnywhere
#
# Spuštění (z adresáře web_app, s nastavenými IMAP_* env):
#   python process_csob_payments.py
#   python process_csob_payments.py --loop --interval 300
#
# Always-on na PA: python process_csob_payments.py --loop --interval 300

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

_WEB_APP = os.path.dirname(os.path.abspath(__file__))
if _WEB_APP not in sys.path:
    sys.path.insert(0, _WEB_APP)
os.chdir(_WEB_APP)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [csob_payments] %(levelname)s %(message)s',
)
logger = logging.getLogger('process_csob_payments')


def _run_once():
    from pdf_check_web_main import app
    from database import Database
    from csob_payments import fetch_and_process_imap

    with app.app_context():
        db = Database()
        res = fetch_and_process_imap(db)
        if not res.get('ok'):
            logger.error('IMAP běh selhal: %s', res.get('error'))
            return 1
        logger.info(
            'Hotovo: processed=%s skipped_non_csob=%s errors=%s',
            res.get('processed'), res.get('skipped_non_csob'), res.get('errors'),
        )
        for r in res.get('results') or []:
            logger.info('  platba=%s stav=%s activated=%s', r.get('platba_id'), r.get('stav'), r.get('activated'))
        return 0


def main():
    parser = argparse.ArgumentParser(description='Zpracování ČSOB avíz z IMAP')
    parser.add_argument('--loop', action='store_true', help='Běžet ve smyčce (Always-on)')
    parser.add_argument('--interval', type=int, default=300, help='Interval smyčky v sekundách (default 300)')
    args = parser.parse_args()

    if not args.loop:
        return _run_once()

    logger.info('Smyčka každých %s s (Ctrl+C ukončí)', args.interval)
    while True:
        try:
            _run_once()
        except Exception:
            logger.exception('Neočekávaná chyba v běhu')
        time.sleep(max(30, int(args.interval)))


if __name__ == '__main__':
    sys.exit(main() or 0)
