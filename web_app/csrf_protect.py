# csrf_protect.py
# Lehká CSRF ochrana pro admin a portálové HTML formuláře (session token).
# API endpointy agenta s Bearer tokenem CSRF nepoužívají.

from __future__ import annotations

import secrets
from functools import wraps

from flask import abort, request, session


CSRF_SESSION_KEY = '_csrf_token'
CSRF_FORM_FIELD = 'csrf_token'
CSRF_HEADER = 'X-CSRF-Token'

# Cesty, kde se CSRF neověřuje (API agenta, veřejné webhooky, statika)
_CSRF_EXEMPT_PREFIXES = (
    '/api/',
    '/static/',
    '/admin/m-dashboard',
)


def get_csrf_token() -> str:
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def validate_csrf_token(token: str | None) -> bool:
    expected = session.get(CSRF_SESSION_KEY)
    if not expected or not token:
        return False
    return secrets.compare_digest(str(token), str(expected))


def _extract_csrf_token() -> str | None:
    token = request.headers.get(CSRF_HEADER)
    if token:
        return token.strip()
    if request.form:
        token = request.form.get(CSRF_FORM_FIELD)
        if token:
            return token.strip()
    if request.is_json:
        data = request.get_json(silent=True) or {}
        if isinstance(data, dict):
            token = data.get(CSRF_FORM_FIELD)
            if token:
                return str(token).strip()
    return None


def should_check_csrf() -> bool:
    if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
        return False
    path = request.path or ''
    for prefix in _CSRF_EXEMPT_PREFIXES:
        if path.startswith(prefix):
            return False
    # Admin UI, login, setup, portál, checkout (ne agent API, ne /app/logout)
    if (
        path.startswith('/admin')
        or path.startswith('/login')
        or path.startswith('/logout')
        or path.startswith('/setup')
        or path.startswith('/portal')
        or path.startswith('/checkout')
    ):
        return True
    return False


def csrf_protect_request():
    """Volat z before_request – při neplatném tokenu vrátí 400."""
    if not should_check_csrf():
        return None
    # Zajistit, že session má token (pro další GET)
    get_csrf_token()
    if not validate_csrf_token(_extract_csrf_token()):
        abort(400, description='Neplatný CSRF token. Obnovte stránku a zkuste znovu.')
    return None
