# mobile_api.py
# Mobilní JSON API pro nativní Android aplikaci DokuCheck Admin.
# Build 141 | © 2026 Ing. Martin Cieślar
#
# Zásady:
# - Vše pod /api/mobile/v1/ (prefix /api/ je mimo CSRF ochranu – ověření je Bearer token zařízení).
# - Přihlášení: jméno + heslo → jednorázový kód e-mailem (stejné funkce jako web) → token zařízení.
# - Token zařízení: náhodný, v DB pouze SHA-256 hash, platnost 90 dní s prodlužováním, kdykoli odvolatelný.
# - Mutující akce se provádějí voláním TÝCH SAMÝCH view funkcí jako webový admin (bez dekorátoru,
#   v interním request kontextu s admin session). Chování i hlášky jsou proto totožné s webem.
# - Čtecí endpointy skládají data ze stejných metod třídy Database jako webové stránky.
# - Odpověď má vždy tvar {"ok": true, "data": ..., "message": ...} nebo {"ok": false, "error": "..."}.
#   Nikdy HTML přesměrování.

from __future__ import annotations

import hashlib
import io
import json
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlparse, parse_qs

from flask import (
    Blueprint, Response, current_app, g, get_flashed_messages, jsonify, request, session,
)
from itsdangerous import BadData, URLSafeTimedSerializer

from database import Database
import admin_routes as AR

MOBILE_API_VERSION = '1.0'
TOKEN_VALID_DAYS = 90
CHALLENGE_MAX_AGE_SECONDS = 600  # stejné jako platnost OTP na webu (10 minut)

mobile_bp = Blueprint('mobile_api', __name__, url_prefix='/api/mobile/v1')


# =============================================================================
# POMOCNÉ FUNKCE – odpovědi
# =============================================================================

def _ok(data=None, message=None, status=200, **extra):
    payload = {'ok': True}
    if data is not None:
        payload['data'] = data
    if message:
        payload['message'] = message
    payload.update(extra)
    return jsonify(payload), status


def _err(message, status=400, code=None, **extra):
    payload = {'ok': False, 'error': message}
    if code:
        payload['code'] = code
    payload.update(extra)
    return jsonify(payload), status


def _body() -> dict:
    """JSON tělo požadavku (nebo form), vždy dict."""
    if request.is_json:
        data = request.get_json(silent=True)
        if isinstance(data, dict):
            return data
        return {}
    if request.form:
        return {k: request.form.get(k) for k in request.form.keys()}
    return {}


def _s(value) -> str:
    return ('' if value is None else str(value)).strip()


def _flag(value) -> str:
    """Převod bool/str na '1' / '0' pro formulářové handlery webu."""
    if isinstance(value, bool):
        return '1' if value else '0'
    return '1' if _s(value).lower() in ('1', 'true', 'ano', 'on', 'yes') else '0'


def _mask_email(addr: str) -> str:
    addr = _s(addr)
    if '@' not in addr:
        return addr
    name, domain = addr.split('@', 1)
    if len(name) <= 2:
        masked = name[0] + '…'
    else:
        masked = name[0] + '…' + name[-1]
    return masked + '@' + domain


def get_db() -> Database:
    return Database()


# =============================================================================
# TABULKA ZAŘÍZENÍ (jediná nová tabulka; vytváří se sama)
# =============================================================================

_schema_ready = False


def ensure_mobile_schema(db: Database = None):
    global _schema_ready
    if _schema_ready:
        return
    db = db or get_db()
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS admin_mobile_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            device_name TEXT,
            platform TEXT,
            app_version TEXT,
            created_at TEXT NOT NULL,
            last_seen TEXT,
            last_ip TEXT,
            expires_at TEXT NOT NULL,
            revoked_at TEXT
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_admin_mobile_devices_admin ON admin_mobile_devices(admin_user_id)')
    conn.commit()
    conn.close()
    _schema_ready = True


def _now() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.isoformat(sep=' ', timespec='seconds')


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', ''))
    except (TypeError, ValueError):
        return None


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _client_ip() -> str:
    fwd = request.headers.get('X-Forwarded-For', '')
    if fwd:
        return fwd.split(',')[0].strip()[:100]
    return (request.remote_addr or '')[:100]


def _create_device(db: Database, admin_user_id: int, device_name: str, platform: str, app_version: str) -> tuple:
    """Vytvoří záznam zařízení a vrátí (token, device_dict)."""
    ensure_mobile_schema(db)
    token = secrets.token_urlsafe(48)
    now = _now()
    expires = now + timedelta(days=TOKEN_VALID_DAYS)
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO admin_mobile_devices
            (admin_user_id, token_hash, device_name, platform, app_version, created_at, last_seen, last_ip, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        int(admin_user_id), _hash_token(token), (device_name or 'Telefon')[:120], (platform or 'android')[:40],
        (app_version or '')[:40], _iso(now), _iso(now), _client_ip(), _iso(expires),
    ))
    device_id = cur.lastrowid
    conn.commit()
    conn.close()
    return token, {
        'id': device_id,
        'device_name': (device_name or 'Telefon')[:120],
        'platform': (platform or 'android')[:40],
        'created_at': _iso(now),
        'expires_at': _iso(expires),
    }


def _find_device_by_token(db: Database, token: str) -> dict | None:
    ensure_mobile_schema(db)
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM admin_mobile_devices WHERE token_hash = ?', (_hash_token(token),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def _touch_device(db: Database, device_id: int, extend: bool):
    now = _now()
    conn = db.get_connection()
    cur = conn.cursor()
    if extend:
        cur.execute(
            'UPDATE admin_mobile_devices SET last_seen = ?, last_ip = ?, expires_at = ? WHERE id = ?',
            (_iso(now), _client_ip(), _iso(now + timedelta(days=TOKEN_VALID_DAYS)), device_id),
        )
    else:
        cur.execute(
            'UPDATE admin_mobile_devices SET last_seen = ?, last_ip = ? WHERE id = ?',
            (_iso(now), _client_ip(), device_id),
        )
    conn.commit()
    conn.close()


def _list_devices(db: Database, admin_user_id: int) -> list:
    ensure_mobile_schema(db)
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT id, device_name, platform, app_version, created_at, last_seen, last_ip, expires_at, revoked_at
        FROM admin_mobile_devices WHERE admin_user_id = ?
        ORDER BY (revoked_at IS NOT NULL), last_seen DESC
    ''', (int(admin_user_id),))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    current_id = (getattr(g, 'mobile_device', None) or {}).get('id')
    for r in rows:
        r['is_current'] = (r['id'] == current_id)
        r['is_revoked'] = bool(r.get('revoked_at'))
    return rows


def _revoke_device(db: Database, admin_user_id: int, device_id: int) -> bool:
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute(
        'UPDATE admin_mobile_devices SET revoked_at = ? WHERE id = ? AND admin_user_id = ? AND revoked_at IS NULL',
        (_iso(_now()), int(device_id), int(admin_user_id)),
    )
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()
    return ok


# =============================================================================
# OVĚŘENÍ TOKENU
# =============================================================================

def mobile_required(f):
    """Vyžaduje platný Bearer token zařízení. Při neúspěchu vrací 401 JSON (nikdy HTML)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        token = auth[7:].strip() if auth.lower().startswith('bearer ') else ''
        if not token:
            return _err('Chybí přihlášení. Přihlaste se v aplikaci.', 401, code='unauthorized')
        db = get_db()
        device = _find_device_by_token(db, token)
        if not device:
            return _err('Přihlášení není platné. Přihlaste se znovu.', 401, code='unauthorized')
        if device.get('revoked_at'):
            return _err('Toto zařízení bylo odhlášeno. Přihlaste se znovu.', 401, code='revoked')
        exp = _parse_iso(device.get('expires_at'))
        if exp and _now() > exp:
            return _err('Platnost přihlášení vypršela. Přihlaste se znovu.', 401, code='expired')
        admin = db.get_admin_by_id(int(device['admin_user_id']))
        if not admin or not admin.get('is_active'):
            return _err('Účet správce není aktivní.', 401, code='unauthorized')
        # Prodloužení platnosti a last_seen (max. jednou za 10 minut kvůli zápisům do DB)
        last_seen = _parse_iso(device.get('last_seen'))
        if not last_seen or (_now() - last_seen) > timedelta(minutes=10):
            _touch_device(db, device['id'], extend=True)
        g.mobile_admin = admin
        g.mobile_device = device
        return f(*args, **kwargs)
    return decorated


def _challenge_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.secret_key, salt='dokucheck-mobile-otp-challenge')


# =============================================================================
# INTERNÍ VOLÁNÍ WEBOVÝCH ADMIN VIEW FUNKCÍ
# =============================================================================

def _call_view(view, method='POST', data=None, query=None, json_body=None, view_kwargs=None, path='/admin/_mobile'):
    """
    Zavolá webovou admin view funkci (bez @admin_required) v interním request kontextu
    s admin session přihlášeného správce. Vrací (návratová hodnota, flash zprávy).
    """
    func = getattr(view, '__wrapped__', view)
    admin = dict(g.mobile_admin)
    kw = {
        'method': method,
        'base_url': request.host_url,
        'environ_base': {'REMOTE_ADDR': request.remote_addr or '127.0.0.1'},
    }
    if query:
        kw['query_string'] = query
    if json_body is not None:
        kw['json'] = json_body
    elif data is not None:
        kw['data'] = data
    with current_app.test_request_context(path, **kw):
        session['admin_user'] = admin
        rv = func(**(view_kwargs or {}))
        flashes = get_flashed_messages(with_categories=True)
    return rv, flashes


def _legacy_json(payload: dict, status: int):
    """Převod {'success':..,'error':..,'message':..,rest} → jednotná obálka."""
    if not isinstance(payload, dict):
        return _ok(payload, status=status)
    p = dict(payload)
    success = p.pop('success', None)
    error = p.pop('error', None)
    message = p.pop('message', None)
    if success is False or (error and success is None):
        code = status if status >= 400 else 400
        return _err(error or message or 'Akce se nezdařila.', code, data=p or None)
    return _ok(p if p else None, message=message, status=200 if status < 400 else status)


def _result(rv, flashes, default_message=None):
    """Sjednotí návrat view funkce (JSON / redirect+flash / soubor) do mobilní odpovědi."""
    status = 200
    resp = rv
    if isinstance(rv, tuple):
        resp = rv[0]
        if len(rv) > 1 and isinstance(rv[1], int):
            status = rv[1]
    if isinstance(resp, Response):
        if resp.is_json:
            return _legacy_json(resp.get_json(silent=True), max(status, resp.status_code))
        if 300 <= resp.status_code < 400:
            errors = [m for c, m in flashes if c == 'error']
            others = [m for c, m in flashes if c != 'error']
            location = resp.headers.get('Location') or ''
            if errors and not others:
                return _err(' '.join(errors), 400, location=location)
            msg = ' '.join(others) if others else default_message
            return _ok(message=msg, warnings=errors or None, location=location)
        # Soubor nebo jiná binární odpověď – vrátit beze změny
        return resp
    # HTML řetězec (view vrátil render_template místo redirectu = chyba validace)
    errors = [m for c, m in flashes if c == 'error']
    if errors:
        return _err(' '.join(errors), 400)
    others = [m for c, m in flashes if c != 'error']
    return _ok(message=' '.join(others) if others else default_message)


def _location_params(location: str) -> dict:
    try:
        return {k: v[0] for k, v in parse_qs(urlparse(location).query).items()}
    except Exception:
        return {}


def _admin_display(admin: dict) -> dict:
    return {
        'id': admin.get('id'),
        'email': admin.get('email'),
        'display_name': admin.get('display_name') or admin.get('email') or 'Admin',
        'role': admin.get('role'),
        'otp_email': admin.get('otp_email'),
        'last_login': admin.get('last_login'),
    }


def _web_version() -> dict:
    try:
        from version import WEB_VERSION, WEB_BUILD
        return {'web_version': WEB_VERSION, 'web_build': WEB_BUILD}
    except Exception:
        return {'web_version': '', 'web_build': 0}


# =============================================================================
# HEALTH (bez přihlášení)
# =============================================================================

@mobile_bp.route('/health', methods=['GET'])
def health():
    db_ok = False
    try:
        db = get_db()
        conn = db.get_connection()
        conn.cursor().execute('SELECT 1').fetchone()
        conn.close()
        ensure_mobile_schema(db)
        db_ok = True
    except Exception:
        db_ok = False
    data = {'server_ok': True, 'db_ok': db_ok, 'api_version': MOBILE_API_VERSION,
            'ts': datetime.utcnow().isoformat(timespec='seconds') + 'Z'}
    data.update(_web_version())
    return _ok(data)


# =============================================================================
# AUTH
# =============================================================================

@mobile_bp.route('/auth/login', methods=['POST'])
def auth_login():
    """Krok 1: jméno + heslo. Odešle kód na OTP e-mail a vrátí podepsaný challenge_token."""
    body = _body()
    login = _s(body.get('email') or body.get('login'))
    password = body.get('password') or ''
    if not login or not password:
        return _err('Vyplňte přihlašovací jméno a heslo.')
    db = get_db()
    ensure_mobile_schema(db)
    ip = _client_ip()
    ok_rate, rate_msg = db.check_admin_bruteforce_ip(ip)
    if not ok_rate:
        return _err(rate_msg, 429)
    success, result = db.verify_admin_password_step(login, password)
    if not success:
        db.record_admin_login_failure(ip)
        return _err(result or 'Neplatné přihlašovací údaje.', 401, code='bad_credentials')
    to_addr = AR._admin_otp_recipient(result)
    if not to_addr or '@' not in to_addr:
        return _err('Účtu chybí platná e-mailová adresa pro ověřovací kód. Nastavte ji ve webovém adminu.', 500)
    plain = f'{secrets.randbelow(900000) + 100000:06d}'
    try:
        ch_id = db.create_admin_login_challenge(result['id'], plain, client_ip=ip)
    except Exception as ex:
        current_app.logger.exception('mobile OTP challenge: %s', ex)
        return _err('Nepodařilo se vytvořit ověření. Zkuste to znovu.', 500)
    if not AR._send_admin_login_otp(to_addr, plain):
        db.record_admin_login_failure(ip)
        return _err('Nepodařilo se odeslat ověřovací e-mail. Zkontrolujte SMTP nastavení serveru.', 500)
    token = _challenge_serializer().dumps({'ch': int(ch_id), 'uid': int(result['id'])})
    return _ok({
        'challenge_token': token,
        'otp_sent_to': _mask_email(to_addr),
        'expires_in': CHALLENGE_MAX_AGE_SECONDS,
    }, message='Na e-mail {} byl odeslán ověřovací kód.'.format(_mask_email(to_addr)))


@mobile_bp.route('/auth/verify', methods=['POST'])
def auth_verify():
    """Krok 2: kód z e-mailu → token zařízení."""
    body = _body()
    ch_token = _s(body.get('challenge_token'))
    code = _s(body.get('code') or body.get('otp_code')).replace(' ', '')
    if not ch_token or not code:
        return _err('Zadejte kód z e-mailu.')
    if len(code) > 12:
        return _err('Neplatný kód.')
    try:
        payload = _challenge_serializer().loads(ch_token, max_age=CHALLENGE_MAX_AGE_SECONDS)
        ch_id = int(payload['ch'])
        uid = int(payload['uid'])
    except (BadData, KeyError, TypeError, ValueError):
        return _err('Platnost ověření vypršela. Přihlaste se znovu heslem.', 401, code='challenge_expired')
    db = get_db()
    ip = _client_ip()
    ok_rate, rate_msg = db.check_admin_bruteforce_ip(ip)
    if not ok_rate:
        return _err(rate_msg, 429)
    ok, user, err_msg = db.verify_admin_login_challenge(ch_id, uid, code)
    if not ok or not user:
        db.record_admin_login_failure(ip)
        fatal = bool(err_msg and ('znovu' in err_msg.lower() or 'vypršela' in err_msg.lower()))
        return _err(err_msg or 'Ověření se nezdařilo.', 401, code='challenge_expired' if fatal else 'bad_code')
    db.record_admin_last_login(user['id'])
    token, device = _create_device(
        db, user['id'],
        device_name=_s(body.get('device_name')) or 'Telefon',
        platform=_s(body.get('platform')) or 'android',
        app_version=_s(body.get('app_version')),
    )
    return _ok({
        'token': token,
        'token_valid_days': TOKEN_VALID_DAYS,
        'device': device,
        'admin': _admin_display(user),
    }, message='Přihlášení proběhlo. Toto zařízení je spárováno.')


@mobile_bp.route('/auth/me', methods=['GET'])
@mobile_required
def auth_me():
    data = {'admin': _admin_display(g.mobile_admin),
            'device': {k: g.mobile_device.get(k) for k in ('id', 'device_name', 'platform', 'created_at', 'expires_at')}}
    data.update(_web_version())
    data['api_version'] = MOBILE_API_VERSION
    return _ok(data)


@mobile_bp.route('/auth/logout', methods=['POST'])
@mobile_required
def auth_logout():
    db = get_db()
    _revoke_device(db, g.mobile_admin['id'], g.mobile_device['id'])
    return _ok(message='Zařízení bylo odhlášeno.')


@mobile_bp.route('/auth/devices', methods=['GET'])
@mobile_required
def auth_devices():
    return _ok(_list_devices(get_db(), g.mobile_admin['id']))


@mobile_bp.route('/auth/devices/revoke', methods=['POST'])
@mobile_required
def auth_devices_revoke():
    body = _body()
    try:
        device_id = int(body.get('device_id'))
    except (TypeError, ValueError):
        return _err('Chybí device_id.')
    if _revoke_device(get_db(), g.mobile_admin['id'], device_id):
        return _ok(message='Zařízení bylo odhlášeno.')
    return _err('Zařízení nenalezeno nebo už bylo odhlášeno.', 404)


@mobile_bp.route('/account/change-password', methods=['POST'])
@mobile_required
def account_change_password():
    body = _body()
    new_pass = body.get('new_password') or ''
    data = {
        'current_password': body.get('current_password') or '',
        'new_password': new_pass,
        'new_password2': body.get('new_password2') or new_pass,
    }
    rv, flashes = _call_view(AR.change_password, data=data)
    return _result(rv, flashes, 'Heslo bylo změněno')


# =============================================================================
# PŘEHLED (DASHBOARD)
# =============================================================================

def _tier_price_map(db):
    return AR._finance_price_by_tier(db)


def _agent_version(db) -> dict:
    agent_build_id = (db.get_global_setting('agent_build_id', '') or '').strip()
    agent_version_display = (db.get_global_setting('agent_version_display', '') or '').strip()
    if not agent_build_id or not agent_version_display:
        try:
            from version import AGENT_BUILD_ID, AGENT_VERSION_DISPLAY
            agent_build_id = agent_build_id or (str(AGENT_BUILD_ID) if AGENT_BUILD_ID is not None else '')
            agent_version_display = agent_version_display or (AGENT_VERSION_DISPLAY or '').strip()
        except Exception:
            pass
    return {'agent_build_id': agent_build_id, 'agent_version_display': agent_version_display}


@mobile_bp.route('/dashboard', methods=['GET'])
@mobile_required
def dashboard():
    """Stejná data jako /admin/dashboard (KPI, grafy, aktivita) + dnešní souhrn."""
    db = get_db()
    licenses = db.admin_get_all_licenses() or []
    stats = {
        'total_licenses': len(licenses),
        'active_licenses': sum(1 for l in licenses if l.get('is_active') and not l.get('is_expired')),
        'expired_licenses': sum(1 for l in licenses if l.get('is_expired')),
        'blocked_licenses': sum(1 for l in licenses if not l.get('is_active')),
        'test_licenses': sum(1 for l in licenses if l.get('is_test')),
        'expiring_30d': sum(1 for l in licenses if l.get('is_active') and not l.get('is_expired')
                            and l.get('days_remaining') is not None and 0 <= int(l.get('days_remaining') or 0) <= 30),
        'total_devices': sum(int(l.get('active_devices') or 0) for l in licenses),
        'total_checks': sum(int(l.get('total_checks') or 0) for l in licenses),
    }
    tiers_list = db.get_all_license_tiers() or []
    by_tier = {}
    for t in tiers_list:
        by_tier[t['name']] = sum(1 for l in licenses if (l.get('tier_id') == t['id']) or (l.get('tier_name') == t['name']))
    # Dnešní objednávky
    today_orders_count, today_orders_amount = 0, 0
    try:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute('''SELECT COUNT(*) AS c, COALESCE(SUM(COALESCE(amount_czk_final, amount_czk)), 0) AS s
                       FROM pending_orders WHERE date(created_at, 'localtime') = date('now', 'localtime')''')
        row = cur.fetchone()
        conn.close()
        if row:
            today_orders_count = int(row['c'] or 0)
            today_orders_amount = int(float(row['s'] or 0))
    except Exception:
        pass
    orders = db.get_pending_orders(limit=500) or []
    pending_count = sum(1 for o in orders if (o.get('status') or '').upper() in ('NEW_ORDER', 'PENDING', 'WAITING_PAYMENT', 'PAYMENT_SENT'))

    def _safe(fn, default):
        try:
            return fn()
        except Exception:
            return default

    data = {
        'stats': stats,
        'by_tier': by_tier,
        'kpis': _safe(db.get_dashboard_kpis, {}),
        'activity_30': _safe(db.get_combined_activity_last_30_days, []),
        'user_ranking': _safe(lambda: db.get_user_activity_ranking(limit=10), []),
        'trial_stats': _safe(db.get_trial_stats, {}),
        'activity_log': _safe(lambda: db.get_activity_log(limit=30), []),
        'activity_stats': _safe(db.get_activity_stats_today, {}),
        'recent_emails': _safe(lambda: db.get_recent_email_logs(limit=10), []),
        'recent_check_results_agent': _safe(lambda: db.get_recent_check_results_with_metadata(limit=15), []),
        'recent_web_checks': _safe(lambda: db.get_activity_log_web_trial_only(limit=15), []),
        'activity_agent_vs_web': _safe(lambda: db.get_activity_agent_vs_web(days=30), {}),
        'web_check_stats': _safe(db.get_web_check_stats_today, {}),
        'today': {
            'orders_count': today_orders_count,
            'orders_amount_czk': today_orders_amount,
            'pending_orders': pending_count,
        },
        'agent': _agent_version(db),
        'revenue': _safe(lambda: db.get_license_revenue_summary(_tier_price_map(db)), {}),
    }
    data.update(_web_version())
    return _ok(data)


@mobile_bp.route('/stats/activity', methods=['GET'])
@mobile_required
def stats_activity():
    db = get_db()
    date_from = _s(request.args.get('from')) or None
    date_to = _s(request.args.get('to')) or None
    if date_from or date_to:
        data = db.get_activity_for_period(date_from=date_from, date_to=date_to)
    else:
        data = db.get_activity_last_30_days()
    return _ok(data)


@mobile_bp.route('/stats/ranking', methods=['GET'])
@mobile_required
def stats_ranking():
    try:
        limit = min(50, max(5, int(request.args.get('limit', 10))))
    except (TypeError, ValueError):
        limit = 10
    return _ok(get_db().get_user_activity_ranking(limit=limit))


@mobile_bp.route('/ops/git-pull', methods=['POST'])
@mobile_required
def ops_git_pull():
    rv, flashes = _call_view(AR.api_git_pull)
    return _result(rv, flashes)


@mobile_bp.route('/agent-version', methods=['GET'])
@mobile_required
def agent_version_get():
    return _ok(_agent_version(get_db()))


@mobile_bp.route('/agent-version', methods=['POST'])
@mobile_required
def agent_version_set():
    body = _body()
    rv, flashes = _call_view(AR.api_mobile_agent_version, json_body={
        'agent_build_id': _s(body.get('agent_build_id')),
        'agent_version_display': _s(body.get('agent_version_display')),
    })
    return _result(rv, flashes, 'Verze agenta uložena')


# =============================================================================
# LICENCE A UŽIVATELÉ
# =============================================================================

_TIER_PRICE_ALIASES = {'firemní': 'firemni', 'standard': 'pro', 'atelier': 'pro', 'atelíér': 'pro', 'projektant': 'basic'}


def _price_label(price_by_tier: dict, lic: dict) -> str:
    tname = (lic.get('tier_name') or '').strip().lower()
    if lic.get('is_test'):
        return '0 Kč (test)'
    if tname in ('trial', 'free', ''):
        return '—'
    p = price_by_tier.get(_TIER_PRICE_ALIASES.get(tname, tname))
    return '{:,.0f} Kč'.format(float(p)).replace(',', ' ') if p else '—'


def _price_value(price_by_tier: dict, lic: dict):
    tname = (lic.get('tier_name') or '').strip().lower()
    if lic.get('is_test') or tname in ('trial', 'free', ''):
        return 0
    p = price_by_tier.get(_TIER_PRICE_ALIASES.get(tname, tname))
    try:
        return int(float(p)) if p else 0
    except (TypeError, ValueError):
        return 0


def _password_plain(db, api_key: str):
    """Uložené heslo uživatele v čitelné podobě (sloupec password_plain_stored), None pokud není."""
    try:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT password_plain_stored FROM api_keys WHERE api_key = ?', (api_key.strip(),))
        row = cur.fetchone()
        conn.close()
        return row['password_plain_stored'] if row and row['password_plain_stored'] else None
    except Exception:
        return None


def _filter_licenses(licenses: list, search: str, tier_filter: str, status_filter: str) -> list:
    out = list(licenses)
    if search:
        s = search.lower()
        out = [l for l in out if (
            (l.get('email') or '').lower().find(s) >= 0
            or (l.get('user_name') or '').lower().find(s) >= 0
            or (l.get('api_key') or '').lower().find(s) >= 0
        )]
    if tier_filter:
        out = [l for l in out if (l.get('tier_name') or '').lower() == tier_filter.lower()]
    if status_filter == 'blocked':
        out = [l for l in out if not l.get('is_active')]
    elif status_filter == 'active':
        out = [l for l in out if l.get('is_active') and not l.get('is_expired')]
    elif status_filter == 'expired':
        out = [l for l in out if l.get('is_expired')]
    elif status_filter == 'test':
        out = [l for l in out if l.get('is_test')]
    elif status_filter == 'expiring':
        out = [l for l in out if l.get('is_active') and not l.get('is_expired')
               and l.get('days_remaining') is not None and 0 <= int(l.get('days_remaining') or 0) <= 30]
    return out


@mobile_bp.route('/licenses', methods=['GET'])
@mobile_required
def licenses_list():
    """Seznam licencí jako na /admin/users-licenses (filtry q, tier, status) + tarify + KPI příjmů."""
    db = get_db()
    search = _s(request.args.get('q'))
    tier_filter = _s(request.args.get('tier'))
    status_filter = _s(request.args.get('status'))
    licenses_all = db.admin_get_all_licenses() or []
    price_by_tier = _tier_price_map(db)
    licenses = _filter_licenses(licenses_all, search, tier_filter, status_filter)
    for l in licenses:
        l['price_label'] = _price_label(price_by_tier, l)
        l['price_czk'] = _price_value(price_by_tier, l)
    tiers_list = db.get_all_license_tiers() or []
    product_tiers = [t for t in tiers_list if (t.get('name') or '').strip().lower() != 'free'] or tiers_list
    try:
        revenue = db.get_license_revenue_summary(price_by_tier)
    except Exception:
        revenue = {}
    return _ok({
        'licenses': licenses,
        'total_all': len(licenses_all),
        'tiers': tiers_list,
        'product_tiers': product_tiers,
        'revenue_summary': revenue,
        'filters': {'q': search, 'tier': tier_filter, 'status': status_filter},
    })


@mobile_bp.route('/licenses/<api_key>', methods=['GET'])
@mobile_required
def license_detail(api_key):
    """Detail uživatele jako /admin/users/detail + heslo v čitelné podobě (je-li uloženo)."""
    db = get_db()
    lic = db.get_user_license(api_key)
    if not lic:
        return _err('Uživatel nenalezen.', 404)
    lic = dict(lic)
    lic.pop('password_hash', None)
    lic.pop('activation_token', None)
    lic.pop('token_expires', None)
    price_by_tier = _tier_price_map(db)
    lic['price_label'] = _price_label(price_by_tier, lic)
    lic['password_plain'] = _password_plain(db, api_key)

    def _safe(fn, default):
        try:
            return fn()
        except Exception:
            return default

    return _ok({
        'license': lic,
        'activity_stats': _safe(lambda: db.get_portal_user_activity_stats(api_key), {}),
        'daily': _safe(lambda: db.get_activity_daily_by_api_key(api_key, days=30), []),
        'recent_files': _safe(lambda: db.get_check_results_by_api_key(api_key, limit=50), []),
        'ips': _safe(lambda: db.get_user_ips(api_key), []),
        'devices': _safe(lambda: db.get_user_devices_list(api_key), []),
        'logs': _safe(lambda: db.get_user_logs(user_id=api_key, limit=100, offset=0), []),
        'billing': _safe(lambda: db.get_billing_history(api_key, limit=50), []),
    })


@mobile_bp.route('/licenses/create', methods=['POST'])
@mobile_required
def license_create():
    body = _body()
    data = {
        'user_name': _s(body.get('user_name')),
        'email': _s(body.get('email')),
        'password': _s(body.get('password')),
        'tier_id': _s(body.get('tier_id')),
        'days': _s(body.get('days')) or '365',
    }
    rv, flashes = _call_view(AR.api_create_license, data=data)
    return _result(rv, flashes)


def _license_update_form(db, api_key: str, body: dict) -> dict:
    """
    Sestaví formulářová pole pro webový handler api_update_license.
    Na rozdíl od webového modalu nepřepisuje feature flagy a limity, které klient nepošle
    (doplní se aktuální hodnoty z licence).
    """
    lic = db.get_user_license(api_key) or {}
    form = {'api_key': api_key}
    for key in ('user_name', 'email', 'license_expires', 'activated_at', 'payment_method', 'last_payment_date', 'new_password', 'tier_id', 'days'):
        if key in body and body.get(key) is not None:
            form[key] = _s(body.get(key))
    # Webový handler bere is_active / is_test jen když jsou přítomné
    if 'is_active' in body and body.get('is_active') is not None:
        form['is_active'] = _flag(body.get('is_active'))
    if 'is_test' in body and body.get('is_test') is not None:
        form['is_test'] = _flag(body.get('is_test'))
    # Feature flagy: pošleme vždy (web je jinak vynuluje)
    for key in ('allow_signatures', 'allow_timestamp', 'allow_excel_export'):
        val = body.get(key) if key in body and body.get(key) is not None else lic.get(key)
        form[key] = _flag(val)
    mbs = body.get('max_batch_size') if 'max_batch_size' in body else lic.get('max_batch_size')
    if mbs not in (None, ''):
        form['max_batch_size'] = _s(mbs)
    if 'max_devices' in body and body.get('max_devices') not in (None, ''):
        form['max_devices'] = _s(body.get('max_devices'))
    # Vynutit „rozšířenou“ větev handleru (ne jen změna tarifu), aby se uložila všechna pole
    if 'user_name' not in form:
        form['user_name'] = _s(lic.get('user_name'))
    if 'email' not in form:
        form['email'] = _s(lic.get('email'))
    return form


@mobile_bp.route('/licenses/<api_key>/update', methods=['POST'])
@mobile_required
def license_update(api_key):
    db = get_db()
    if not db.get_user_license(api_key):
        return _err('Licence nenalezena.', 404)
    body = _body()
    form = _license_update_form(db, api_key, body)
    rv, flashes = _call_view(AR.api_update_license, data=form)
    return _result(rv, flashes, 'Licence aktualizována')


@mobile_bp.route('/licenses/<api_key>/set-tier', methods=['POST'])
@mobile_required
def license_set_tier(api_key):
    """Rychlá změna tarifu (stejná větev jako dropdown na webu)."""
    body = _body()
    tier_id = _s(body.get('tier_id'))
    if not tier_id:
        return _err('Chybí tier_id.')
    rv, flashes = _call_view(AR.api_update_license, data={'api_key': api_key, 'tier_id': tier_id})
    return _result(rv, flashes)


@mobile_bp.route('/licenses/<api_key>/extend', methods=['POST'])
@mobile_required
def license_extend(api_key):
    """Prodloužení platnosti o N dní (od data konce, nebo od dneška, je-li licence vypršelá)."""
    db = get_db()
    lic = db.get_user_license(api_key)
    if not lic:
        return _err('Licence nenalezena.', 404)
    body = _body()
    raw_days = body.get('days')
    try:
        days = 365 if raw_days in (None, '') else int(raw_days)
    except (TypeError, ValueError):
        return _err('Neplatný počet dní.')
    if days <= 0 or days > 3650:
        return _err('Počet dní musí být 1 až 3650.')
    base = datetime.now()
    cur = _parse_iso((lic.get('license_expires') or '')[:19].replace('T', ' ')) if lic.get('license_expires') else None
    if cur and cur > base:
        base = cur
    new_exp = (base + timedelta(days=days)).strftime('%Y-%m-%d')
    ok = db.admin_update_user_full(api_key, license_expires=new_exp)
    if not ok:
        return _err('Prodloužení se nezdařilo.', 500)
    try:
        db.insert_payment_log(api_key, 'prodlouzeni', details='+{} dní → {}'.format(days, new_exp))
    except Exception:
        pass
    return _ok({'license_expires': new_exp}, message='Platnost prodloužena do {}.'.format(new_exp))


@mobile_bp.route('/licenses/<api_key>/toggle', methods=['POST'])
@mobile_required
def license_toggle(api_key):
    body = _body()
    rv, flashes = _call_view(AR.api_toggle_license, data={'api_key': api_key, 'is_active': _flag(body.get('is_active'))})
    return _result(rv, flashes)


@mobile_bp.route('/licenses/<api_key>/set-test', methods=['POST'])
@mobile_required
def license_set_test(api_key):
    body = _body()
    rv, flashes = _call_view(AR.api_set_license_test, data={'api_key': api_key, 'is_test': _flag(body.get('is_test'))})
    return _result(rv, flashes)


@mobile_bp.route('/licenses/<api_key>/set-password', methods=['POST'])
@mobile_required
def license_set_password(api_key):
    body = _body()
    pwd = _s(body.get('new_password'))
    rv, flashes = _call_view(AR.api_set_license_password, data={
        'api_key': api_key, 'new_password': pwd, 'new_password2': _s(body.get('new_password2')) or pwd,
    })
    return _result(rv, flashes)


@mobile_bp.route('/licenses/<api_key>/delete', methods=['POST'])
@mobile_required
def license_delete(api_key):
    rv, flashes = _call_view(AR.api_delete_license, data={'api_key': api_key})
    return _result(rv, flashes)


@mobile_bp.route('/licenses/<api_key>/welcome-package', methods=['GET'])
@mobile_required
def license_welcome_package(api_key):
    rv, flashes = _call_view(AR.api_welcome_package, data={'api_key': api_key})
    res = _result(rv, flashes)
    # Doplnit uložené heslo (webový handler ho kvůli chybě v get_license_password_plain nikdy nenačte)
    try:
        resp, status = res
        payload = resp.get_json(silent=True) or {}
        pwd = _password_plain(get_db(), api_key)
        if payload.get('ok') and pwd and isinstance(payload.get('data'), dict):
            body_txt = payload['data'].get('email_body') or ''
            lines = [('Heslo: ' + pwd) if ln.startswith('Heslo: ') else ln for ln in body_txt.split('\n')]
            payload['data']['email_body'] = '\n'.join(lines)
            payload['data']['password_plain'] = pwd
            return jsonify(payload), status
    except Exception:
        pass
    return res


@mobile_bp.route('/licenses/<api_key>/devices', methods=['GET'])
@mobile_required
def license_devices(api_key):
    rv, flashes = _call_view(AR.api_get_user_devices, method='GET', query={'api_key': api_key})
    return _result(rv, flashes)


@mobile_bp.route('/licenses/<api_key>/devices/<action>', methods=['POST'])
@mobile_required
def license_device_action(api_key, action):
    views = {'block': AR.api_block_user_device, 'unblock': AR.api_unblock_user_device, 'remove': AR.api_remove_user_device}
    view = views.get(action)
    if not view:
        return _err('Neznámá akce zařízení.', 404)
    body = _body()
    rv, flashes = _call_view(view, data={'api_key': api_key, 'machine_id': _s(body.get('machine_id'))})
    return _result(rv, flashes)


@mobile_bp.route('/licenses/<api_key>/reset-devices', methods=['POST'])
@mobile_required
def license_reset_devices(api_key):
    rv, flashes = _call_view(AR.api_reset_devices, data={'api_key': api_key})
    return _result(rv, flashes)


@mobile_bp.route('/licenses/<api_key>/billing', methods=['GET'])
@mobile_required
def license_billing_list(api_key):
    rv, flashes = _call_view(AR.api_license_billing_list, method='GET', query={'api_key': api_key})
    return _result(rv, flashes)


@mobile_bp.route('/licenses/<api_key>/billing', methods=['POST'])
@mobile_required
def license_billing_add(api_key):
    body = _body()
    data = {'api_key': api_key}
    for key in ('description', 'amount_cents', 'amount_czk', 'paid_at', 'period_year', 'invoice_kind'):
        if body.get(key) not in (None, ''):
            data[key] = _s(body.get(key))
    rv, flashes = _call_view(AR.api_license_billing_add, data=data)
    return _result(rv, flashes)


@mobile_bp.route('/licenses/<api_key>/audit', methods=['GET'])
@mobile_required
def license_audit(api_key):
    db = get_db()
    q = _s(request.args.get('q')) or None
    try:
        limit = min(1000, max(10, int(request.args.get('limit', 500))))
    except (TypeError, ValueError):
        limit = 500
    logs = db.get_user_logs(user_id=api_key, limit=limit, offset=0, search=q)
    return _ok({'logs': logs, 'count': len(logs)})


# =============================================================================
# OBJEDNÁVKY
# =============================================================================

_ORDER_STATUS_LABELS = {
    'NEW_ORDER': 'Objednáno', 'PENDING': 'Objednáno',
    'PAYMENT_SENT': 'Čeká na zaplacení', 'WAITING_PAYMENT': 'Čeká na zaplacení',
    'ACTIVE': 'Aktivní licence',
}


def _enrich_orders(db, orders_raw, licenses_all=None):
    try:
        from settings_loader import get_tarif_display_name, normalize_tarif_slug
    except Exception:
        def normalize_tarif_slug(s, default='pro'):
            x = (s or default).strip().lower()
            return 'pro' if x == 'standard' else x

        def get_tarif_display_name(db_, slug):
            return {'basic': 'Basic', 'pro': 'Pro', 'firemni': 'Firemní'}.get(normalize_tarif_slug(slug), (slug or '').capitalize())
    if licenses_all is None:
        licenses_all = db.admin_get_all_licenses() or []
    active_emails = {(l.get('email') or '').lower(): l for l in licenses_all
                     if l.get('is_active') and (l.get('tier_name') or '').lower() not in ('trial', 'free')}
    out = []
    for o in (orders_raw or []):
        d = dict(o)
        t = normalize_tarif_slug(d.get('tarif'))
        d['tarif'] = t
        d['tarif_label'] = get_tarif_display_name(db, t)
        email = (d.get('email') or '').lower()
        d['has_active_license'] = email in active_emails
        d['api_key'] = active_emails.get(email, {}).get('api_key') if email in active_emails else None
        st = (d.get('status') or '').upper()
        d['status_label'] = _ORDER_STATUS_LABELS.get(st, d.get('status') or '')
        d['is_pending'] = st in ('NEW_ORDER', 'PENDING')
        d['is_waiting'] = st in ('PAYMENT_SENT', 'WAITING_PAYMENT')
        d['is_active'] = st == 'ACTIVE'
        d['has_invoice'] = bool(d.get('invoice_path') and os.path.isfile(d.get('invoice_path') or ''))
        d['amount_display'] = d.get('amount_czk_final') if d.get('amount_czk_final') is not None else d.get('amount_czk')
        out.append(d)
    return out


@mobile_bp.route('/orders', methods=['GET'])
@mobile_required
def orders_list():
    db = get_db()
    status_filter = _s(request.args.get('status')).lower()  # pending | waiting | active | ''
    orders = _enrich_orders(db, db.get_pending_orders(limit=500))
    if status_filter == 'pending':
        orders = [o for o in orders if o['is_pending']]
    elif status_filter == 'waiting':
        orders = [o for o in orders if o['is_waiting']]
    elif status_filter == 'active':
        orders = [o for o in orders if o['is_active']]
    try:
        auto_activate = db.get_setting_bool('auto_activate_csob', False)
    except Exception:
        auto_activate = False
    return _ok({
        'orders': orders,
        'auto_activate_csob': auto_activate,
        'env_labels': AR._get_env_labels(db),
        'counts': {
            'pending': sum(1 for o in orders if o['is_pending']),
            'waiting': sum(1 for o in orders if o['is_waiting']),
            'active': sum(1 for o in orders if o['is_active']),
        },
    })


@mobile_bp.route('/orders/<int:order_id>', methods=['GET'])
@mobile_required
def order_detail(order_id):
    db = get_db()
    order = db.get_pending_order_by_id(order_id)
    if not order:
        return _err('Objednávka nenalezena.', 404)
    enriched = _enrich_orders(db, [order])[0]
    return _ok(enriched)


@mobile_bp.route('/orders/<int:order_id>/edit', methods=['POST'])
@mobile_required
def order_edit(order_id):
    db = get_db()
    order = db.get_pending_order_by_id(order_id)
    if not order:
        return _err('Objednávka nenalezena.', 404)
    body = _body()
    fields = ('jmeno_firma', 'ico', 'email', 'tarif', 'ulice', 'mesto', 'psc', 'dic', 'order_display_number', 'amount_czk', 'amount_czk_final')
    data = {}
    for key in fields:
        # Webový formulář posílá všechna pole; chybějící doplníme z objednávky
        val = body.get(key) if key in body else order.get(key)
        data[key] = '' if val is None else str(val)
    rv, flashes = _call_view(AR.edit_pending_order, data=data, view_kwargs={'order_id': order_id})
    return _result(rv, flashes, 'Objednávka byla upravena.')


@mobile_bp.route('/orders/<int:order_id>/delete', methods=['POST'])
@mobile_required
def order_delete(order_id):
    rv, flashes = _call_view(AR.delete_pending_order, data={'order_id': str(order_id)})
    return _result(rv, flashes)


@mobile_bp.route('/orders/bulk-delete', methods=['POST'])
@mobile_required
def orders_bulk_delete():
    ids = _body().get('order_ids') or []
    if isinstance(ids, str):
        ids = [x for x in ids.split(',') if x.strip()]
    rv, flashes = _call_view(AR.bulk_delete_orders, data={'order_ids': ','.join(str(i) for i in ids)})
    return _result(rv, flashes)


@mobile_bp.route('/orders/<int:order_id>/send-payment', methods=['POST'])
@mobile_required
def order_send_payment(order_id):
    rv, flashes = _call_view(AR.api_mobile_order_send_payment, json_body={'order_id': str(order_id)})
    res = _result(rv, flashes)
    return res


@mobile_bp.route('/orders/bulk-send-payment', methods=['POST'])
@mobile_required
def orders_bulk_send_payment():
    ids = _body().get('order_ids') or []
    if isinstance(ids, str):
        ids = [x for x in ids.split(',') if x.strip()]
    rv, flashes = _call_view(AR.bulk_send_payment, data={'order_ids': ','.join(str(i) for i in ids)})
    return _result(rv, flashes)


@mobile_bp.route('/orders/email-preview', methods=['GET'])
@mobile_required
def order_email_preview():
    """type=payment|activation, order_id, api_key. POZOR: activation bez api_key vytvoří licenci (stejně jako web)."""
    query = {
        'type': _s(request.args.get('type')),
        'order_id': _s(request.args.get('order_id')),
        'api_key': _s(request.args.get('api_key')),
    }
    rv, flashes = _call_view(AR.api_email_preview, method='GET', query=query)
    return _result(rv, flashes)


@mobile_bp.route('/orders/email-send', methods=['POST'])
@mobile_required
def order_email_send():
    body = _body()
    data = {
        'recipient': _s(body.get('recipient')),
        'subject': _s(body.get('subject')),
        'body': (body.get('body') or '').strip(),
        'action_type': _s(body.get('action_type')),
        'order_id': _s(body.get('order_id')),
        'api_key': _s(body.get('api_key')),
        'attach_invoice': _flag(body.get('attach_invoice')),
    }
    rv, flashes = _call_view(AR.api_email_send, data=data)
    return _result(rv, flashes, 'E-mail odeslán.')


def _order_action(view, order_id, default_message=None):
    rv, flashes = _call_view(view, data={'order_id': str(order_id)})
    res = _result(rv, flashes, default_message)
    # Přidat api_key/order_id z přesměrování (confirm-payment / activate-without-invoice)
    try:
        resp, status = res
        payload = resp.get_json(silent=True) or {}
        loc = payload.get('location') or ''
        if payload.get('ok') and 'preview-activation-email' in loc:
            params = _location_params(loc)
            payload['data'] = {'api_key': params.get('api_key'), 'order_id': params.get('order_id')}
            return jsonify(payload), status
    except Exception:
        pass
    return res


@mobile_bp.route('/orders/<int:order_id>/generate-invoice', methods=['POST'])
@mobile_required
def order_generate_invoice(order_id):
    return _order_action(AR.generate_invoice, order_id)


@mobile_bp.route('/orders/<int:order_id>/regenerate-invoice', methods=['POST'])
@mobile_required
def order_regenerate_invoice(order_id):
    return _order_action(AR.regenerate_invoice, order_id)


@mobile_bp.route('/orders/<int:order_id>/apply-discount', methods=['POST'])
@mobile_required
def order_apply_discount(order_id):
    return _order_action(AR.apply_discount, order_id)


@mobile_bp.route('/orders/<int:order_id>/confirm-payment', methods=['POST'])
@mobile_required
def order_confirm_payment(order_id):
    return _order_action(AR.confirm_payment, order_id)


@mobile_bp.route('/orders/<int:order_id>/activate-without-invoice', methods=['POST'])
@mobile_required
def order_activate_without_invoice(order_id):
    return _order_action(AR.activate_without_invoice, order_id)


@mobile_bp.route('/orders/<int:order_id>/delete-user', methods=['POST'])
@mobile_required
def order_delete_user(order_id):
    return _order_action(AR.delete_user_from_order, order_id)


@mobile_bp.route('/orders/<int:order_id>/invoice.pdf', methods=['GET'])
@mobile_required
def order_invoice_pdf(order_id):
    rv, flashes = _call_view(AR.download_invoice, method='GET', view_kwargs={'order_id': order_id})
    if isinstance(rv, Response) and 300 <= rv.status_code < 400:
        errors = [m for c, m in flashes if c == 'error'] or ['Faktura nebyla nalezena.']
        return _err(' '.join(errors), 404)
    return rv


@mobile_bp.route('/orders/auto-activate-csob', methods=['GET'])
@mobile_required
def auto_activate_get():
    db = get_db()
    try:
        val = db.get_setting_bool('auto_activate_csob', False)
    except Exception:
        val = False
    return _ok({'auto_activate_csob': val})


@mobile_bp.route('/orders/auto-activate-csob', methods=['POST'])
@mobile_required
def auto_activate_set():
    body = _body()
    rv, flashes = _call_view(AR.toggle_auto_activate_csob, data={'auto_activate_csob': _flag(body.get('value', body.get('auto_activate_csob')))})
    return _result(rv, flashes)


# =============================================================================
# ČSOB PLATBY
# =============================================================================

@mobile_bp.route('/csob', methods=['GET'])
@mobile_required
def csob_list():
    db = get_db()
    stav = _s(request.args.get('stav')) or None
    platby = db.list_csob_platby(stav=stav, limit=300) or []
    for p in platby:
        try:
            p['castka_czk'] = round(int(p.get('castka_haleru') or 0) / 100.0, 2)
        except (TypeError, ValueError):
            p['castka_czk'] = None
        p['stav_label'] = AR._CSOB_STAV_LABELS.get(p.get('stav'), p.get('stav'))
        p.pop('raw_email', None)
    try:
        auto_activate = db.get_setting_bool('auto_activate_csob', False)
    except Exception:
        auto_activate = False
    waiting = []
    seen = set()
    for st in ('WAITING_PAYMENT', 'payment_sent', 'NEW_ORDER', 'pending'):
        for o in (db.get_pending_orders(status=st, limit=100) or []):
            if o.get('id') in seen:
                continue
            seen.add(o.get('id'))
            waiting.append({k: o.get(k) for k in ('id', 'order_display_number', 'jmeno_firma', 'email', 'tarif', 'status', 'amount_czk', 'amount_czk_final', 'created_at')})
    try:
        from csob_payments import get_imap_status
        imap_status = get_imap_status()
    except Exception:
        imap_status = {'configured': False, 'password_set': False, 'dkimpy_installed': False}
    return _ok({
        'platby': platby,
        'stav_labels': AR._CSOB_STAV_LABELS,
        'stav_filter': stav or '',
        'auto_activate_csob': auto_activate,
        'waiting_orders': waiting,
        'imap_status': imap_status,
    })


@mobile_bp.route('/csob/<int:platba_id>/sparovat', methods=['POST'])
@mobile_required
def csob_sparovat(platba_id):
    body = _body()
    rv, flashes = _call_view(AR.csob_platby_sparovat, data={'order_id': _s(body.get('order_id'))}, view_kwargs={'platba_id': platba_id})
    return _result(rv, flashes)


@mobile_bp.route('/csob/<int:platba_id>/aktivovat', methods=['POST'])
@mobile_required
def csob_aktivovat(platba_id):
    rv, flashes = _call_view(AR.csob_platby_aktivovat, data={}, view_kwargs={'platba_id': platba_id})
    return _result(rv, flashes)


@mobile_bp.route('/csob/<int:platba_id>/vyridit', methods=['POST'])
@mobile_required
def csob_vyridit(platba_id):
    rv, flashes = _call_view(AR.csob_platby_vyridit, data={}, view_kwargs={'platba_id': platba_id})
    return _result(rv, flashes)


@mobile_bp.route('/csob/manual', methods=['POST'])
@mobile_required
def csob_manual():
    body = _body()
    data = {k: _s(body.get(k)) for k in ('variabilni_symbol', 'castka_czk', 'protiucet', 'datum_zauctovani', 'zprava_pro_prijemce', 'poznamka', 'mena')}
    rv, flashes = _call_view(AR.csob_platby_manual, data=data)
    return _result(rv, flashes)


@mobile_bp.route('/csob/process-imap', methods=['POST'])
@mobile_required
def csob_process_imap():
    body = _body()
    rv, flashes = _call_view(AR.csob_platby_process_imap, data={'include_seen': _flag(body.get('include_seen'))})
    return _result(rv, flashes)


@mobile_bp.route('/csob/test-imap', methods=['POST'])
@mobile_required
def csob_test_imap():
    rv, flashes = _call_view(AR.csob_platby_test_imap, data={})
    return _result(rv, flashes)


@mobile_bp.route('/csob/upload-eml', methods=['POST'])
@mobile_required
def csob_upload_eml():
    f = request.files.get('eml_file')
    if not f or not f.filename:
        return _err('Vyberte soubor .eml.')
    raw = f.read()
    skip = _flag(request.form.get('skip_dkim'))
    data = {'skip_dkim': skip, 'eml_file': (io.BytesIO(raw), f.filename)}
    rv, flashes = _call_view(AR.csob_platby_upload_eml, data=data)
    return _result(rv, flashes)


# =============================================================================
# FINANCE
# =============================================================================

@mobile_bp.route('/finance', methods=['GET'])
@mobile_required
def finance():
    db = get_db()
    price_by_tier = _tier_price_map(db)
    years = db.get_finance_years() or [datetime.now().year]
    current_year = datetime.now().year
    year = request.args.get('year', type=int)
    if not year or year not in years:
        year = current_year if current_year in years else years[0]
    q = _s(request.args.get('q'))
    summary = db.get_finance_summary(year, price_by_tier)
    monthly = db.get_finance_monthly_revenue(year, price_by_tier)
    invoices = db.get_invoices_list(year=year, q=q, price_by_tier=price_by_tier) or []
    try:
        from settings_loader import get_tarif_display_name, normalize_tarif_slug
    except Exception:
        def normalize_tarif_slug(s, default='pro'):
            x = (s or default).strip().lower()
            return 'pro' if x == 'standard' else x

        def get_tarif_display_name(db_, slug):
            return {'basic': 'Basic', 'pro': 'Pro', 'firemni': 'Firemní'}.get(normalize_tarif_slug(slug), (slug or '').capitalize())
    for inv in invoices:
        inv['tarif_label'] = get_tarif_display_name(db, normalize_tarif_slug(inv.get('tarif')))
        path = (inv.get('invoice_path') or '').strip()
        inv['has_pdf'] = bool(path and os.path.isfile(path))
    total_shown = sum(inv.get('amount') or 0 for inv in invoices)
    return _ok({
        'summary': summary,
        'monthly_revenue': monthly,
        'invoices': invoices,
        'total_shown': total_shown,
        'year': year,
        'years': years,
        'q': q,
    })


@mobile_bp.route('/finance/invoices.zip', methods=['GET'])
@mobile_required
def finance_zip():
    year = request.args.get('year', type=int) or datetime.now().year
    rv, flashes = _call_view(AR.finance_invoices_zip, method='GET', query={'year': str(year)})
    if isinstance(rv, Response) and 300 <= rv.status_code < 400:
        errors = [m for c, m in flashes if c == 'error'] or ['Žádné faktury.']
        return _err(' '.join(errors), 404)
    return rv


# =============================================================================
# TARIFY
# =============================================================================

def _tier_form(body: dict) -> dict:
    data = {}
    for key in ('name', 'max_files_limit', 'max_devices', 'daily_files_limit', 'rate_limit_hour', 'max_file_size_mb', 'checkout_features'):
        if body.get(key) is not None:
            data[key] = _s(body.get(key))
    for key in ('allow_signatures', 'allow_timestamp', 'allow_excel_export', 'allow_advanced_filters'):
        data[key] = _flag(body.get(key))
    return data


@mobile_bp.route('/tiers', methods=['GET'])
@mobile_required
def tiers_list():
    return _ok(get_db().get_all_license_tiers() or [])


@mobile_bp.route('/tiers/add', methods=['POST'])
@mobile_required
def tiers_add():
    rv, flashes = _call_view(AR.api_add_tier, data=_tier_form(_body()))
    return _result(rv, flashes)


@mobile_bp.route('/tiers/<int:tier_id>/update', methods=['POST'])
@mobile_required
def tiers_update(tier_id):
    data = _tier_form(_body())
    data['tier_id'] = str(tier_id)
    rv, flashes = _call_view(AR.api_update_tier, data=data)
    return _result(rv, flashes)


# =============================================================================
# TRIAL, WEB KONTROLY (IP), FREE CHECK
# =============================================================================

@mobile_bp.route('/trial', methods=['GET'])
@mobile_required
def trial_get():
    db = get_db()
    return _ok({
        'trial_list': db.list_trial_usage() or [],
        'web_trial_list': db.list_web_trial_usage() or [],
        'web_trial_files_limit': db.get_web_trial_files_limit(),
        'trial_stats': db.get_trial_stats(),
    })


@mobile_bp.route('/trial/limit', methods=['POST'])
@mobile_required
def trial_limit():
    body = _body()
    rv, flashes = _call_view(AR.trial, data={'action': 'save_web_trial_limit', 'web_trial_max_files_per_month': _s(body.get('limit') or body.get('web_trial_max_files_per_month'))})
    return _result(rv, flashes)


@mobile_bp.route('/trial/reset', methods=['POST'])
@mobile_required
def trial_reset():
    body = _body()
    rv, flashes = _call_view(AR.api_trial_reset, json_body={'machine_id': _s(body.get('machine_id'))})
    return _result(rv, flashes)


@mobile_bp.route('/web-trial/reset', methods=['POST'])
@mobile_required
def web_trial_reset():
    body = _body()
    rv, flashes = _call_view(AR.api_web_trial_reset, json_body={'ip_address': _s(body.get('ip_address'))})
    return _result(rv, flashes)


@mobile_bp.route('/web-checks', methods=['GET'])
@mobile_required
def web_checks():
    db = get_db()
    rows = db.list_web_check_ips() or []
    known = {r['ip_address'] for r in rows}
    legacy = []
    for l in (db.list_web_trial_usage() or []):
        if l['ip_address'] not in known:
            blk = db.get_ip_block(l['ip_address']) or {}
            legacy.append({
                'ip_address': l['ip_address'], 'total_checks': l.get('total_batches') or 0,
                'total_files': None, 'files_month': None, 'files_24h': None, 'checks_24h': None,
                'limit_hits': 0, 'active_days': 1, 'first_seen': None, 'last_seen': l.get('last_used'),
                'blocked_until': blk.get('blocked_until'), 'block_reason': blk.get('reason'), 'is_legacy': True,
            })
    all_rows = rows + legacy
    all_rows.sort(key=lambda r: (r.get('total_files') if r.get('total_files') is not None else r.get('total_checks') or 0), reverse=True)
    return _ok({
        'rows': all_rows,
        'stats': db.get_web_check_stats_today(),
        'files_limit': db.get_web_trial_files_limit(),
    })


@mobile_bp.route('/web-checks/ip', methods=['GET'])
@mobile_required
def web_check_ip():
    db = get_db()
    ip = _s(request.args.get('ip'))
    if not ip:
        return _err('Chybí IP adresa.')
    logs = db.get_web_check_log_by_ip(ip, limit=500) or []
    daily = db.get_web_check_daily_by_ip(ip, days=30)
    block = db.get_ip_block(ip)
    _, files_24h, files_limit = db.check_web_check_file_limit(ip, incoming_files=1)
    stats = {
        'total_checks': len(logs),
        'total_files': sum((l.get('file_count') or 0) for l in logs if l.get('status') == 'ok'),
        'limit_hits': sum(1 for l in logs if l.get('status') == 'limit'),
        'total_size': sum((l.get('total_size') or 0) for l in logs),
        'first_seen': logs[-1]['timestamp'] if logs else None,
        'last_seen': logs[0]['timestamp'] if logs else None,
        'files_24h': files_24h,
    }
    return _ok({'ip': ip, 'logs': logs, 'daily': daily, 'block': block, 'stats': stats, 'files_limit': files_limit})


@mobile_bp.route('/web-checks/limit', methods=['POST'])
@mobile_required
def web_checks_limit():
    body = _body()
    rv, flashes = _call_view(AR.web_checks, data={'action': 'save_web_check_limit', 'web_trial_max_files_per_month': _s(body.get('limit') or body.get('web_trial_max_files_per_month'))})
    return _result(rv, flashes)


@mobile_bp.route('/ip-block', methods=['POST'])
@mobile_required
def ip_block():
    body = _body()
    data = {
        'ip_address': _s(body.get('ip_address')),
        'block_action': _s(body.get('action') or body.get('block_action')) or 'block',
        'hours': _s(body.get('hours')) or '24',
    }
    rv, flashes = _call_view(AR.api_ip_block, data=data)
    return _result(rv, flashes)


@mobile_bp.route('/web-check/reset', methods=['POST'])
@mobile_required
def web_check_reset():
    body = _body()
    rv, flashes = _call_view(AR.api_web_check_reset, data={'ip_address': _s(body.get('ip_address'))})
    return _result(rv, flashes)


@mobile_bp.route('/free-check-usage', methods=['GET'])
@mobile_required
def free_check_usage():
    db = get_db()
    try:
        hours = int(request.args.get('hours', 24))
    except (TypeError, ValueError):
        hours = 24
    if hours not in (6, 12, 24, 48):
        hours = 24
    limit_per_hour = 3
    usage = db.get_free_check_usage_by_ip(hours=hours, limit_per_hour=limit_per_hour)
    return _ok({'usage': usage, 'hours': hours, 'limit_per_hour': limit_per_hour})


# =============================================================================
# LOGY, NÁVŠTĚVNOST
# =============================================================================

@mobile_bp.route('/logs', methods=['GET'])
@mobile_required
def logs():
    db = get_db()
    category = _s(request.args.get('category')) or 'activity'
    if category not in ('system', 'user', 'payment', 'activity'):
        category = 'activity'
    user_id = _s(request.args.get('user_id')) or None
    date_from = _s(request.args.get('date_from')) or None
    date_to = _s(request.args.get('date_to')) or None
    level = _s(request.args.get('level')) or None
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    per_page = 100
    offset = (page - 1) * per_page
    if category == 'activity':
        logs_list = db.get_activity_log(limit=500) or []
        if date_from or date_to:
            def parse_dt(s):
                try:
                    return datetime.strptime(s[:10], '%Y-%m-%d').date()
                except Exception:
                    return None
            start = parse_dt(date_from) if date_from else None
            end = parse_dt(date_to) if date_to else None
            filtered = []
            for row in logs_list:
                ts = row.get('timestamp') or ''
                try:
                    row_date = datetime.strptime(ts[:10], '%Y-%m-%d').date() if len(ts) >= 10 else None
                except Exception:
                    row_date = None
                if not row_date:
                    continue
                if start and row_date < start:
                    continue
                if end and row_date > end:
                    continue
                filtered.append(row)
            logs_list = filtered
        total = len(logs_list)
        logs_list = logs_list[offset:offset + per_page]
    else:
        logs_list = db.get_logs_filtered(category=category, user_id=user_id, date_from=date_from, date_to=date_to,
                                         level=level, limit=per_page, offset=offset) or []
        total = None
        if category in ('payment', 'system') and logs_list:
            user_ids = {log.get('user_id') for log in logs_list if log.get('user_id')}
            display_map = {}
            for uid in user_ids:
                lic = db.get_user_license(uid) if uid else None
                display_map[uid] = (lic.get('user_name') or lic.get('email') or uid) if lic else uid
            for log in logs_list:
                log['user_display'] = display_map.get(log.get('user_id'), log.get('user_id'))
    return _ok({
        'logs': logs_list, 'category': category, 'page': page, 'per_page': per_page,
        'total': total, 'has_more': len(logs_list) == per_page,
    })


@mobile_bp.route('/analytics', methods=['GET'])
@mobile_required
def analytics():
    db = get_db()
    try:
        days = int(request.args.get('days', 30))
    except (TypeError, ValueError):
        days = 30
    if days not in (7, 14, 30, 90):
        days = 30

    def _safe(fn, default):
        try:
            return fn()
        except Exception:
            return default

    devices = _safe(lambda: db.get_device_breakdown(days=days), [])
    device_total = sum(d.get('views', 0) for d in devices) or 1
    device_share = {d['device_type']: round(100.0 * d.get('views', 0) / device_total, 1) for d in devices}
    return _ok({
        'days': days,
        'stats': _safe(db.get_page_views_stats, {}),
        'by_page': _safe(lambda: db.get_page_views_by_page(days=days), []),
        'by_referrer': _safe(lambda: db.get_page_views_by_referrer(days=days), []),
        'by_utm': _safe(lambda: db.get_page_views_by_utm(days=days), []),
        'daily': _safe(lambda: db.get_page_views_daily(days=days), []),
        'hourly': _safe(lambda: db.get_page_views_hourly(hours=24), []),
        'devices': devices,
        'device_share': device_share,
        'new_vs_returning': _safe(lambda: db.get_new_vs_returning(days=days), {}),
        'visitor_paths': _safe(lambda: db.get_visitor_paths(days=min(days, 14), limit=25), []),
        'funnel': _safe(lambda: db.get_conversion_funnel(days=days), {}),
        'recent_views': _safe(lambda: db.get_recent_page_views(hours=24, limit=40), []),
    })


# =============================================================================
# OBSAH WEBU
# =============================================================================

@mobile_bp.route('/content/faq', methods=['GET'])
@mobile_required
def content_faq():
    return _ok(get_db().get_all_faq() or [])


@mobile_bp.route('/content/faq/add', methods=['POST'])
@mobile_required
def content_faq_add():
    body = _body()
    rv, flashes = _call_view(AR.faq_add, data={'question': _s(body.get('question')), 'answer': (body.get('answer') or '').strip(), 'order_index': _s(body.get('order_index')) or '0'})
    return _result(rv, flashes, 'Dotaz byl přidán.')


@mobile_bp.route('/content/faq/<int:faq_id>/update', methods=['POST'])
@mobile_required
def content_faq_update(faq_id):
    body = _body()
    rv, flashes = _call_view(AR.faq_edit, data={'question': _s(body.get('question')), 'answer': (body.get('answer') or '').strip(), 'order_index': _s(body.get('order_index')) or '0'}, view_kwargs={'faq_id': faq_id})
    return _result(rv, flashes, 'Dotaz byl upraven.')


@mobile_bp.route('/content/faq/<int:faq_id>/delete', methods=['POST'])
@mobile_required
def content_faq_delete(faq_id):
    rv, flashes = _call_view(AR.faq_delete, data={'faq_id': str(faq_id)})
    return _result(rv, flashes)


@mobile_bp.route('/content/updates', methods=['GET'])
@mobile_required
def content_updates():
    db = get_db()
    landing_updates = db.get_setting_json('landing_updates', AR.DEFAULT_LANDING_UPDATES)
    if not isinstance(landing_updates, list):
        landing_updates = list(AR.DEFAULT_LANDING_UPDATES)
    return _ok({'landing_updates': landing_updates, 'download_whats_new': db.get_global_setting('download_whats_new', '') or ''})


@mobile_bp.route('/content/updates', methods=['POST'])
@mobile_required
def content_updates_save():
    """action: save_updates_json {landing_updates:[...]}, save_download_whats_new {download_whats_new}, add_entry {month,title,items}, delete_entry {index}"""
    body = _body()
    action = _s(body.get('action'))
    data = {'action': action}
    if action == 'save_updates_json':
        data['landing_updates_json'] = json.dumps(body.get('landing_updates') or [], ensure_ascii=False)
    elif action == 'save_download_whats_new':
        data['download_whats_new'] = body.get('download_whats_new') or ''
    elif action == 'add_entry':
        items = body.get('items')
        if isinstance(items, list):
            items = '\n'.join(str(x) for x in items)
        data.update({'month': _s(body.get('month')), 'title': _s(body.get('title')), 'items': items or ''})
    elif action == 'delete_entry':
        data['index'] = _s(body.get('index'))
    else:
        return _err('Neznámá akce.')
    rv, flashes = _call_view(AR.updates, data=data)
    return _result(rv, flashes)


@mobile_bp.route('/content/coming-soon', methods=['GET'])
@mobile_required
def content_coming_soon():
    db = get_db()
    return _ok({'cards': AR._get_coming_soon_cards_for_admin(db), 'intro': db.get_global_setting('coming_soon_intro', '') or ''})


@mobile_bp.route('/content/coming-soon', methods=['POST'])
@mobile_required
def content_coming_soon_save():
    body = _body()
    if 'cards' in body:
        cards = body.get('cards') or []
        data = {
            'action': 'save_coming_soon_cards',
            'title': [_s(c.get('title')) for c in cards],
            'subtitle': [_s(c.get('subtitle')) for c in cards],
            'items': [(c.get('items') or '') for c in cards],
            'benefit': [_s(c.get('benefit')) for c in cards],
            'color': [_s(c.get('color')) or 'blue' for c in cards],
        }
        rv, flashes = _call_view(AR.coming_soon, data=data)
        res = _result(rv, flashes)
        if 'intro' not in body:
            return res
    if 'intro' in body:
        rv, flashes = _call_view(AR.coming_soon, data={'action': 'save_intro', 'coming_soon_intro': body.get('intro') or ''})
        return _result(rv, flashes)
    return _err('Nic k uložení.')


@mobile_bp.route('/content/marketing-emails', methods=['GET'])
@mobile_required
def content_marketing_emails():
    try:
        from site_config_loader import get_email_templates
        templates = get_email_templates() or {}
    except Exception:
        templates = {}
    return _ok(templates)


@mobile_bp.route('/content/marketing-emails', methods=['POST'])
@mobile_required
def content_marketing_emails_save():
    body = _body()
    data = {k: (body.get(k) or '') for k in ('footer_text', 'order_confirmation_subject', 'order_confirmation_body', 'activation_subject', 'activation_body')}
    data['from_page'] = 'marketing'
    rv, flashes = _call_view(AR.save_email_templates_route, data=data)
    return _result(rv, flashes)


@mobile_bp.route('/content/marketing-emails/test', methods=['POST'])
@mobile_required
def content_marketing_emails_test():
    body = _body()
    rv, flashes = _call_view(AR.send_test_email_route, data={'test_email_to': _s(body.get('to'))})
    return _result(rv, flashes)


@mobile_bp.route('/content/checkout-texts', methods=['GET'])
@mobile_required
def content_checkout_texts():
    from settings_loader import CHECKOUT_PRICING_TEXT_KEYS, get_checkout_pricing_texts
    db = get_db()
    return _ok({'keys': list(CHECKOUT_PRICING_TEXT_KEYS), 'texts': get_checkout_pricing_texts(db)})


@mobile_bp.route('/content/checkout-texts', methods=['POST'])
@mobile_required
def content_checkout_texts_save():
    from settings_loader import CHECKOUT_PRICING_TEXT_KEYS, get_checkout_pricing_texts
    db = get_db()
    body = _body()
    current = get_checkout_pricing_texts(db)
    data = {}
    for key in CHECKOUT_PRICING_TEXT_KEYS:
        data[key] = body.get(key) if key in body else (current.get(key) or '')
    rv, flashes = _call_view(AR.checkout_texts, data=data)
    return _result(rv, flashes)


_COMPANY_KEYS = ('provider_name', 'provider_address', 'provider_ico', 'provider_bank_name', 'bank_account', 'bank_iban',
                 'provider_phone', 'provider_email', 'provider_trade_register', 'invoices_dir')
_COMPANY_DEFAULTS = {
    'provider_name': 'Ing. Martin Cieślar', 'provider_address': 'Porubská 1, 742 83 Klimkovice', 'provider_ico': '04830661',
    'provider_bank_name': 'ČSOB',
    'provider_trade_register': 'Fyzická osoba zapsaná v Živnostenském rejstříku vedeném na Magistrátu města Ostrava.',
}


@mobile_bp.route('/content/company', methods=['GET'])
@mobile_required
def content_company():
    db = get_db()
    return _ok({k: (db.get_global_setting(k, '') or _COMPANY_DEFAULTS.get(k, '')) for k in _COMPANY_KEYS})


@mobile_bp.route('/content/company', methods=['POST'])
@mobile_required
def content_company_save():
    db = get_db()
    body = _body()
    data = {}
    for k in _COMPANY_KEYS:
        data[k] = body.get(k) if k in body else (db.get_global_setting(k, '') or '')
    rv, flashes = _call_view(AR.company_settings, data=data)
    return _result(rv, flashes)


@mobile_bp.route('/content/help', methods=['GET'])
@mobile_required
def content_help():
    db = get_db()
    return _ok({'info_card_content': db.get_site_setting('info_card_content', ''), 'help_card_content': db.get_site_setting('help_card_content', '')})


@mobile_bp.route('/content/help', methods=['POST'])
@mobile_required
def content_help_save():
    db = get_db()
    body = _body()
    saved = 0
    for key in ('info_card_content', 'help_card_content'):
        if body.get(key) is not None:
            db.set_site_setting(key, (body.get(key) or '').replace('​', ''))
            saved += 1
    if not saved:
        return _err('Nic k uložení.')
    return _ok(message='Nápověda uložena.')


# =============================================================================
# NASTAVENÍ (Global Config)
# =============================================================================

_SETTINGS_ACTIONS = {
    'global': ('maintenance_mode', 'allow_new_registrations'),
    'save_contact': ('contact_email', 'contact_phone'),
    'save_download_url': ('download_url', 'download_agent_updated_at'),
    'save_basic': ('provider_name', 'provider_address', 'provider_ico', 'provider_legal_note', 'contact_email', 'contact_phone', 'bank_account', 'bank_iban'),
    'save_sales': ('price_basic', 'price_pro', 'price_firemni', 'landing_tarif_basic_desc', 'landing_tarif_pro_desc', 'landing_tarif_firemni_desc',
                   'payment_instructions', 'pilot_notice_text', 'show_pilot_notice', 'turnstile_site_key', 'turnstile_secret_key', 'checkout_auto_send_customer_email'),
    'save_pricing': ('pricing_tarifs_json', 'trial_limit_total_files'),
    'save_marketing': ('landing_hero_title', 'landing_hero_subtitle', 'landing_hero_badge', 'landing_cta_primary', 'landing_cta_secondary',
                       'landing_section_how_title', 'landing_section_modes_title', 'landing_mode_agent_title', 'landing_mode_agent_text',
                       'landing_mode_cloud_title', 'landing_mode_cloud_text', 'landing_tarif_basic_desc', 'landing_tarif_standard_desc', 'landing_tarif_premium_desc',
                       'landing_how_steps_json', 'landing_faq_json', 'testimonials_json', 'partner_logos_json', 'top_promo_bar_json', 'exit_intent_popup_json'),
    'save_legal': ('legal_vop_html', 'legal_gdpr_html', 'footer_disclaimer', 'app_legal_notice'),
    'save_environment': ('order_number_prefix', 'order_number_next', 'label_status_new', 'label_status_waiting_payment', 'label_status_active',
                         'label_section_new_orders', 'label_section_waiting_payment', 'label_section_active_licenses', 'label_menu_pending_orders',
                         'label_btn_obednat', 'label_btn_confirm_payment', 'label_btn_activate', 'label_btn_activate_without_invoice'),
    'save_coming_soon': ('coming_soon_intro', 'coming_soon_path_title', 'coming_soon_path_subtitle', 'coming_soon_path_items', 'coming_soon_path_benefit',
                         'coming_soon_editor_title', 'coming_soon_editor_subtitle', 'coming_soon_editor_items', 'coming_soon_editor_benefit',
                         'coming_soon_zpf_title', 'coming_soon_zpf_subtitle', 'coming_soon_zpf_items', 'coming_soon_zpf_benefit',
                         'coming_soon_parking_title', 'coming_soon_parking_subtitle', 'coming_soon_parking_items', 'coming_soon_parking_benefit'),
    'save_mail': ('mail_server', 'mail_port', 'mail_username', 'mail_default_sender', 'order_notification_email', 'admin_info_email'),
    'save_system': ('seo_meta_title', 'seo_meta_description', 'email_order_confirmation_subject', 'email_order_confirmation_body',
                    'email_welcome_subject', 'email_welcome_body', 'analysis_timeout_seconds', 'header_scripts_json', 'allowed_extensions_json'),
    'password': ('current_password', 'new_password', 'new_password2'),
}
_SETTINGS_BOOL_KEYS = ('maintenance_mode', 'allow_new_registrations', 'show_pilot_notice', 'checkout_auto_send_customer_email')
_SETTINGS_JSON_KEYS = ('pricing_tarifs_json', 'landing_how_steps_json', 'landing_faq_json', 'testimonials_json', 'partner_logos_json',
                       'top_promo_bar_json', 'exit_intent_popup_json', 'header_scripts_json', 'allowed_extensions_json')


@mobile_bp.route('/settings', methods=['GET'])
@mobile_required
def settings_get():
    db = get_db()
    st = AR._settings_for_admin(db)
    st['env_labels'] = AR._get_env_labels(db)
    # Prodejní ceny pro záložku Správa prodeje
    pricing = st.get('pricing_tarifs') or {}
    st['price_basic'] = (pricing.get('basic') or {}).get('amount_czk') if isinstance(pricing, dict) else None
    st['price_pro'] = (pricing.get('pro') or {}).get('amount_czk') if isinstance(pricing, dict) else None
    st['price_firemni'] = (pricing.get('firemni') or {}).get('amount_czk') if isinstance(pricing, dict) else None
    st['landing_tarif_firemni_desc'] = db.get_global_setting('landing_tarif_firemni_desc', '') or ''
    st['actions'] = {k: list(v) for k, v in _SETTINGS_ACTIONS.items()}
    st['turnstile_secret_key'] = '***' if st.get('turnstile_secret_key') else ''
    return _ok(st)


@mobile_bp.route('/settings/<action>', methods=['POST'])
@mobile_required
def settings_save(action):
    keys = _SETTINGS_ACTIONS.get(action)
    if not keys:
        return _err('Neznámá záložka nastavení.', 404)
    body = _body()
    data = {'action': action}
    for key in keys:
        if key not in body:
            continue
        val = body.get(key)
        if key in _SETTINGS_BOOL_KEYS:
            data[key] = _flag(val)
        elif key in _SETTINGS_JSON_KEYS:
            if isinstance(val, (dict, list)):
                data[key] = json.dumps(val, ensure_ascii=False)
            else:
                raw = _s(val)
                if raw:
                    try:
                        json.loads(raw)
                    except (json.JSONDecodeError, TypeError) as e:
                        return _err('Neplatný JSON v poli {}: {}'.format(key, e))
                data[key] = raw
        else:
            data[key] = '' if val is None else str(val)
    if action == 'save_sales' and 'turnstile_secret_key' in data and data['turnstile_secret_key'] == '***':
        data['turnstile_secret_key'] = get_db().get_global_setting('turnstile_secret_key', '') or ''
    # Bool pole u akce 'global'/'save_sales' web vyhodnocuje podle přítomnosti '1' – chybějící = vypnuto,
    # proto je doplníme z aktuálního stavu, když klient klíč neposlal.
    if action in ('global', 'save_sales'):
        db = get_db()
        for key in _SETTINGS_BOOL_KEYS:
            if key in keys and key not in data:
                data[key] = '1' if db.get_setting_bool(key, key == 'allow_new_registrations') else '0'
    rv, flashes = _call_view(AR.settings, data=data)
    return _result(rv, flashes, 'Nastavení uloženo')
