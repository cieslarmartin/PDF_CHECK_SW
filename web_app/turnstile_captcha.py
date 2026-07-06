# turnstile_captcha.py – ověření Cloudflare Turnstile na checkoutu
import logging
import os

import requests

TURNSTILE_VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
_logger = logging.getLogger(__name__)


def get_turnstile_keys(db=None):
    """Site key a secret: env má přednost, fallback global_settings."""
    site_key = (os.environ.get('TURNSTILE_SITE_KEY') or '').strip()
    secret_key = (os.environ.get('TURNSTILE_SECRET_KEY') or '').strip()
    if db is not None:
        if not site_key:
            site_key = (db.get_global_setting('turnstile_site_key') or '').strip()
        if not secret_key:
            secret_key = (db.get_global_setting('turnstile_secret_key') or '').strip()
    return site_key, secret_key


def is_turnstile_enabled(db=None):
    site_key, secret_key = get_turnstile_keys(db)
    return bool(site_key and secret_key)


def verify_turnstile(token, remote_ip=None, db=None):
    """Ověří token z formuláře. Vrátí (ok: bool, error_message: str|None)."""
    _site_key, secret_key = get_turnstile_keys(db)
    if not secret_key:
        return False, 'CAPTCHA není nakonfigurována na serveru.'
    token = (token or '').strip()
    if not token:
        return False, 'Chybí token CAPTCHA.'
    payload = {'secret': secret_key, 'response': token}
    if remote_ip:
        payload['remoteip'] = remote_ip
    try:
        resp = requests.post(TURNSTILE_VERIFY_URL, data=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        _logger.warning('Turnstile verify request failed: %s', exc)
        return False, 'Ověření CAPTCHA se nepodařilo. Zkuste to znovu.'
    if data.get('success'):
        return True, None
    codes = data.get('error-codes') or []
    _logger.info('Turnstile rejected token: %s', codes)
    return False, 'Ověření CAPTCHA se nezdařilo. Zkuste to znovu.'
