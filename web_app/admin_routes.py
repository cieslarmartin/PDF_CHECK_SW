# admin_routes.py
# Admin routes pro PDF DokuCheck - správa licencí
# Build 41 | © 2025 Ing. Martin Cieślar
#
# Tento modul poskytuje:
# - /login - Přihlášení
# - /logout - Odhlášení
# - /admin - Admin dashboard pro správu licencí

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
import os
import subprocess
import json
from datetime import datetime, timedelta

# Import databáze
try:
    from database import Database, generate_api_key
except ImportError:
    Database = None

# Import settings loader pro Admin Nastavení (global_settings)
try:
    from settings_loader import load_settings_for_views
except ImportError:
    load_settings_for_views = None

# Import license config
try:
    from license_config import LicenseTier, tier_to_string, TIER_NAMES
except ImportError:
    class LicenseTier:
        FREE = 0
        BASIC = 1
        PRO = 2
        ENTERPRISE = 3
    TIER_NAMES = {0: "Free", 1: "Basic", 2: "Pro", 3: "Enterprise"}
    def tier_to_string(t): return TIER_NAMES.get(t, "Free")


# Blueprint pro admin routes
admin_bp = Blueprint('admin', __name__)

# Secret key pro sessions (v produkci použít silný klíč)
ADMIN_SECRET_KEY = os.environ.get('ADMIN_SECRET_KEY', 'pdfcheck_admin_secret_2025')


def get_db():
    """Získá instanci databáze"""
    return Database()


def login_required(f):
    """Dekorátor: DOČASNĚ VYPNOUT – vždy propustí (viz admin_required)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_user' not in session:
            session['admin_user'] = {
                'id': 0,
                'email': 'admin@admin.cz',
                'role': 'ADMIN',
                'display_name': 'Admin (bez přihlášení)',
            }
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Dekorátor: DOČASNĚ VYPNOUT – vždy propustí bez přihlášení (heslo vyřešíme až na konci projektu)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_user' not in session:
            session['admin_user'] = {
                'id': 0,
                'email': 'admin@admin.cz',
                'role': 'ADMIN',
                'display_name': 'Admin (bez přihlášení)',
            }
        return f(*args, **kwargs)
    return decorated_function


# =============================================================================
# VÝCHOZÍ ADMIN A PŘÍSTUP K DASHBOARDU
# =============================================================================

# Výchozí přihlašovací údaje pro admin dashboard (login + všechny admin funkce)
DEFAULT_ADMIN_EMAIL = 'admin@admin.cz'
DEFAULT_ADMIN_PASSWORD = 'admin'


def get_default_admin_credentials():
    """Vrátí (email, heslo) pro přístup k admin dashboardu a všem admin funkcím."""
    return (DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)


def ensure_default_admin():
    """
    Zajistí, že v DB existuje admin účet admin@admin.cz s heslem 'admin'.
    NATVRDO: vždy nastaví zahashované heslo 'admin' (PBKDF2-HMAC-SHA256 dle database.py).
    Volá se při načtení přihlašovací stránky – po přihlášení máte přístup k dashboardu
    (/admin, /admin/dashboard) a všem admin funkcím.
    """
    db = get_db()
    user = db.get_admin_by_email(DEFAULT_ADMIN_EMAIL)
    if user:
        db.update_admin_user(user['id'], password=DEFAULT_ADMIN_PASSWORD)
        return True
    success, _ = db.create_admin_user(
        email=DEFAULT_ADMIN_EMAIL,
        password=DEFAULT_ADMIN_PASSWORD,
        role='ADMIN',
        display_name='Admin'
    )
    return success


def reset_default_admin_password():
    """Nastaví heslo účtu admin@admin.cz na 'admin'. Vrací True pokud účet existoval a byl aktualizován."""
    db = get_db()
    user = db.get_admin_by_email(DEFAULT_ADMIN_EMAIL)
    if not user:
        return False
    return db.update_admin_user(user['id'], password=DEFAULT_ADMIN_PASSWORD)


# =============================================================================
# AUTH ROUTES
# =============================================================================

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Přihlašovací stránka"""
    ensure_default_admin()
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Vyplňte email a heslo', 'error')
            return render_template('admin_login.html')

        db = get_db()
        success, result = db.verify_admin_login(email, password)
        user_exists = db.get_admin_by_email(email) is not None

        if success:
            session['admin_user'] = result
            session.permanent = True
            flash(f'Vítejte, {result.get("display_name", email)}!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            print("LOGIN ATTEMPT: Email [{}], Password length [{}]".format(email, len(password)))
            print("DB STATUS: Existuje uživatel? [{}], Výsledek verify_admin_login: [{}]".format(user_exists, success))
            flash(result, 'error')

    return render_template('admin_login.html')


@admin_bp.route('/logout')
def logout():
    """Odhlášení"""
    session.pop('admin_user', None)
    flash('Byli jste odhlášeni', 'info')
    return redirect(url_for('admin.login'))


# =============================================================================
# ADMIN DASHBOARD
# =============================================================================

@admin_bp.route('/admin')
@admin_bp.route('/admin/dashboard')
@admin_required
def dashboard():
    """Admin dashboard - správa licencí, KPI, přepínatelné grafy."""
    db = get_db()

    # Filtry: vyhledávání, tarif, stav
    search = (request.args.get('q') or '').strip()
    tier_filter = (request.args.get('tier') or '').strip()
    status_filter = (request.args.get('status') or '').strip()  # active, blocked

    licenses = db.admin_get_all_licenses()

    if search:
        search_lower = search.lower()
        licenses = [l for l in licenses if (
            (l.get('email') or '').lower().find(search_lower) >= 0 or
            (l.get('user_name') or '').lower().find(search_lower) >= 0 or
            (l.get('api_key') or '').lower().find(search_lower) >= 0
        )]
    if tier_filter:
        licenses = [l for l in licenses if (l.get('tier_name') or '').lower() == tier_filter.lower()]
    if status_filter == 'blocked':
        licenses = [l for l in licenses if not l.get('is_active')]
    elif status_filter == 'active':
        licenses = [l for l in licenses if l.get('is_active')]

    stats = {
        'total_licenses': len(licenses),
        'active_licenses': sum(1 for l in licenses if l.get('is_active') and not l.get('is_expired')),
        'expired_licenses': sum(1 for l in licenses if l.get('is_expired')),
        'total_devices': sum(l.get('active_devices', 0) for l in licenses),
        'total_checks': sum(l.get('total_checks', 0) for l in licenses),
        'by_tier': {}
    }
    for tier in LicenseTier:
        stats['by_tier'][tier.name] = sum(1 for l in licenses if l.get('license_tier') == tier.value)

    activity_30_raw = db.get_activity_last_30_days()
    # Vyplnit všech 30 dní (0 kde chybí) pro sloupcový graf
    today = datetime.utcnow().date()
    day_map = {r['date']: r['files'] for r in (activity_30_raw or [])}
    activity_30 = []
    for i in range(29, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        activity_30.append({'date': d, 'files': day_map.get(d, 0)})
    tiers_list = db.get_all_license_tiers()
    # Pro nové licence nabízíme pouze Free, Basic, Pro, Trial (bez Enterprise)
    product_tiers = [t for t in tiers_list if (t.get('name') or '').strip() in ('Trial', 'Basic', 'Pro', 'Unlimited')]
    if not product_tiers:
        product_tiers = tiers_list
    by_tier_counts = {}
    for t in tiers_list:
        by_tier_counts[t['name']] = sum(1 for l in licenses if (l.get('tier_id') == t['id']) or (l.get('tier_name') == t['name']))
    for t in tiers_list:
        if t['name'] not in by_tier_counts:
            by_tier_counts[t['name']] = 0

    kpis = db.get_dashboard_kpis()
    user_ranking = db.get_user_activity_ranking(limit=10)
    trial_stats = db.get_trial_stats()
    online_demo_log = db.get_online_demo_log(limit=200)

    user = session.get('admin_user') or {}
    if not user.get('display_name'):
        user = dict(user)
        user['display_name'] = user.get('email') or 'Admin'
    return render_template('admin_dashboard.html',
                          licenses=licenses,
                          stats=stats,
                          tiers=TIER_NAMES,
                          tiers_list=tiers_list or [],
                          product_tiers=product_tiers,
                          activity_30=activity_30 or [],
                          by_tier_counts=by_tier_counts or {},
                          kpis=kpis,
                          user_ranking=user_ranking or [],
                          trial_stats=trial_stats or {},
                          online_demo_log=online_demo_log or [],
                          search=search,
                          tier_filter=tier_filter,
                          status_filter=status_filter,
                          user=user,
                          active_page='dashboard')


@admin_bp.route('/admin/users')
@admin_required
def users():
    """Přesměruje na dashboard (hlavní pohled na uživatele)."""
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/admin/users/audit')
@admin_required
def user_audit():
    """User Audit: logy pro konkrétního uživatele (user_id = api_key v query)."""
    db = get_db()
    user_id = request.args.get('user', '').strip()
    if not user_id:
        flash('Zadejte uživatele (parametr user)', 'error')
        return redirect(url_for('admin.dashboard'))
    logs = db.get_user_logs(user_id=user_id, limit=500, offset=0, search=request.args.get('q', '').strip())
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute('SELECT email, user_name FROM api_keys WHERE api_key = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    user_email = row['email'] if row else (user_id[:20] + '...')
    user_display = (row['user_name'] or row['email']) if row else (user_id[:20] + '...')
    user = session.get('admin_user') or {}
    if not user.get('display_name'):
        user = dict(user)
        user['display_name'] = user.get('email') or 'Admin'
    return render_template('admin_user_audit.html', logs=logs, user_id=user_id, user_email=user_email, user_display=user_display, user=user, active_page='dashboard')


@admin_bp.route('/admin/tiers')
@admin_required
def tiers():
    """Globální definice tierů (Free, Basic, Pro, Enterprise) – pouze úprava limitů, ne per-user."""
    db = get_db()
    tiers_list = db.get_all_license_tiers()
    user = session.get('admin_user') or {}
    if not user.get('display_name'):
        user = dict(user)
        user['display_name'] = user.get('email') or 'Admin'
    return render_template('admin_tiers.html', tiers_list=tiers_list or [], user=user, active_page='tiers')


@admin_bp.route('/admin/pending-orders')
@admin_required
def pending_orders():
    """Čekající objednávky (fakturační formulář – Čeká na platbu)."""
    db = get_db()
    orders = db.get_pending_orders(status=None, limit=200)
    user = session.get('admin_user') or {}
    if not user.get('display_name'):
        user = dict(user)
        user['display_name'] = user.get('email') or 'Admin'
    return render_template('admin_pending_orders.html', orders=orders or [], user=user, active_page='pending_orders')


@admin_bp.route('/admin/trial')
@admin_required
def trial():
    """Správa Trial použití: Machine-ID | Celkem souborů | Poslední aktivita | Reset."""
    db = get_db()
    trial_list = db.list_trial_usage()
    user = session.get('admin_user') or {}
    if not user.get('display_name'):
        user = dict(user)
        user['display_name'] = user.get('email') or 'Admin'
    return render_template('admin_trial.html', trial_list=trial_list or [], user=user, active_page='trial')


@admin_bp.route('/admin/logs')
@admin_required
def logs():
    """Logy: Systémové / Uživatelské / Platební s filtry (datum, úroveň, uživatel)."""
    db = get_db()
    category = request.args.get('category', 'user').strip() or 'user'
    if category not in ('system', 'user', 'payment'):
        category = 'user'
    user_id = request.args.get('user_id', '').strip() or None
    date_from = request.args.get('date_from', '').strip() or None
    date_to = request.args.get('date_to', '').strip() or None
    level = request.args.get('level', '').strip() or None
    page = max(1, int(request.args.get('page', 1)))
    per_page = 100
    offset = (page - 1) * per_page
    logs_list = db.get_logs_filtered(
        category=category, user_id=user_id, date_from=date_from, date_to=date_to,
        level=level, limit=per_page, offset=offset
    )
    # Pro platební a systémové logy doplnit zobrazené jméno (user_display) z api_keys
    if category in ('payment', 'system') and logs_list:
        user_ids = {log.get('user_id') for log in logs_list if log.get('user_id')}
        display_map = {}
        for uid in user_ids:
            lic = db.get_user_license(uid) if uid else None
            display_map[uid] = (lic.get('user_name') or lic.get('email') or uid) if lic else uid
        for log in logs_list:
            log['user_display'] = display_map.get(log.get('user_id'), log.get('user_id'))
    user = session.get('admin_user') or {}
    if not user.get('display_name'):
        user = dict(user)
        user['display_name'] = user.get('email') or 'Admin'
    return render_template('admin_logs.html',
                          logs_list=logs_list,
                          category=category,
                          user_id=user_id or '',
                          date_from=date_from or '',
                          date_to=date_to or '',
                          level=level or '',
                          page=page,
                          per_page=per_page,
                          user=user,
                          active_page='logs')


def _settings_for_admin(db):
    """Načte všechna nastavení pro Admin stránku Nastavení (s fallbacky)."""
    if load_settings_for_views:
        return load_settings_for_views(db)
    s = {}
    for key in ('provider_name', 'provider_address', 'provider_ico', 'provider_legal_note', 'contact_email', 'contact_phone',
                'bank_account', 'bank_iban', 'landing_hero_title', 'landing_hero_subtitle', 'landing_hero_badge',
                'landing_cta_primary', 'landing_cta_secondary', 'landing_section_how_title', 'landing_section_modes_title',
                'landing_mode_agent_title', 'landing_mode_agent_text', 'landing_mode_cloud_title', 'landing_mode_cloud_text',
                'landing_tarif_basic_desc', 'landing_tarif_standard_desc', 'landing_tarif_premium_desc',
                'footer_disclaimer', 'app_legal_notice', 'seo_meta_title', 'seo_meta_description',
                'email_order_confirmation_subject', 'email_order_confirmation_body', 'email_welcome_subject', 'email_welcome_body'):
        s[key] = db.get_global_setting(key, '')
    s['maintenance_mode'] = db.get_setting_bool('maintenance_mode', False)
    s['allow_new_registrations'] = db.get_setting_bool('allow_new_registrations', True)
    s['trial_limit_total_files'] = db.get_setting_int('trial_limit_total_files', 10)
    s['analysis_timeout_seconds'] = db.get_setting_int('analysis_timeout_seconds', 300)
    s['pricing_tarifs'] = db.get_setting_json('pricing_tarifs', {'basic': {'label': 'BASIC', 'amount_czk': 1290}, 'standard': {'label': 'PRO', 'amount_czk': 1990}})
    s['payment_instructions'] = db.get_global_setting('payment_instructions', '')
    s['pilot_notice_text'] = db.get_global_setting('pilot_notice_text', '') or ''
    s['show_pilot_notice'] = db.get_setting_bool('show_pilot_notice', True)
    s['landing_how_steps'] = db.get_setting_json('landing_how_steps', [])
    s['landing_faq'] = db.get_setting_json('landing_faq', [])
    s['legal_vop_html'] = db.get_global_setting('legal_vop_html', '')
    s['legal_gdpr_html'] = db.get_global_setting('legal_gdpr_html', '')
    s['download_url'] = db.get_global_setting('download_url', '')
    s['testimonials'] = db.get_setting_json('testimonials', [])
    s['partner_logos'] = db.get_setting_json('partner_logos', [])
    s['top_promo_bar'] = db.get_setting_json('top_promo_bar', {'text': '', 'background_color': '#1e5a8a', 'is_active': False})
    s['exit_intent_popup'] = db.get_setting_json('exit_intent_popup', {'title': '', 'body': '', 'button_text': 'Zavřít', 'is_active': False})
    s['header_scripts'] = db.get_setting_json('header_scripts', [])
    s['allowed_extensions'] = db.get_setting_json('allowed_extensions', ['.pdf'])
    return s


@admin_bp.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    """Global Config: záložky Základní, Ceny, Marketing, Právní, Systém + údržba a změna hesla."""
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action', '')
        if action == 'password':
            current = request.form.get('current_password', '')
            new_pass = request.form.get('new_password', '')
            new_pass2 = request.form.get('new_password2', '')
            if not current or not new_pass or not new_pass2:
                flash('Vyplňte všechna pole hesla', 'error')
            elif new_pass != new_pass2:
                flash('Nové heslo a potvrzení se neshodují', 'error')
            elif len(new_pass) < 6:
                flash('Nové heslo musí mít alespoň 6 znaků', 'error')
            else:
                email = session.get('admin_user', {}).get('email')
                ok, _ = db.verify_admin_login(email, current)
                if not ok:
                    flash('Aktuální heslo není správné', 'error')
                else:
                    uid = session.get('admin_user', {}).get('id')
                    if db.update_admin_user(uid, password=new_pass):
                        flash('Heslo bylo změněno', 'success')
                    else:
                        flash('Nepodařilo se změnit heslo', 'error')
        elif action == 'global':
            maintenance = request.form.get('maintenance_mode') == '1'
            allow_reg = request.form.get('allow_new_registrations') == '1'
            db.set_global_setting('maintenance_mode', maintenance)
            db.set_global_setting('allow_new_registrations', allow_reg)
            flash('Globální nastavení uloženo', 'success')
        elif action == 'save_contact':
            db.set_global_setting('contact_email', request.form.get('contact_email', ''))
            db.set_global_setting('contact_phone', request.form.get('contact_phone', ''))
            flash('Kontakt uložen', 'success')
        elif action == 'save_download_url':
            db.set_global_setting('download_url', (request.form.get('download_url') or '').strip())
            flash('URL stažení uložena', 'success')
        elif action == 'save_basic':
            for key in ('provider_name', 'provider_address', 'provider_ico', 'provider_legal_note', 'contact_email', 'contact_phone', 'bank_account', 'bank_iban'):
                db.set_global_setting(key, request.form.get(key, ''))
            flash('Základní nastavení uloženo', 'success')
        elif action == 'save_sales':
            # Správa prodeje: ceny BASIC/PRO, texty ceníku, platební instrukce
            try:
                price_basic = request.form.get('price_basic', '')
                price_pro = request.form.get('price_pro', '')
                pricing = db.get_setting_json('pricing_tarifs', {'basic': {'label': 'BASIC', 'amount_czk': 1290}, 'standard': {'label': 'PRO', 'amount_czk': 1990}})
                if not isinstance(pricing, dict):
                    pricing = {'basic': {'label': 'BASIC', 'amount_czk': 1290}, 'standard': {'label': 'PRO', 'amount_czk': 1990}}
                if price_basic.strip():
                    amt = int(price_basic)
                    if 'basic' not in pricing:
                        pricing['basic'] = {'label': 'BASIC', 'amount_czk': amt}
                    else:
                        pricing['basic']['amount_czk'] = amt
                if price_pro.strip():
                    amt = int(price_pro)
                    if 'standard' not in pricing:
                        pricing['standard'] = {'label': 'PRO', 'amount_czk': amt}
                    else:
                        pricing['standard']['amount_czk'] = amt
                        pricing['standard']['label'] = 'PRO'
                db.set_global_setting('pricing_tarifs', pricing)
            except (ValueError, TypeError):
                pass
            db.set_global_setting('landing_tarif_basic_desc', request.form.get('landing_tarif_basic_desc', ''))
            db.set_global_setting('landing_tarif_standard_desc', request.form.get('landing_tarif_pro_desc', ''))
            db.set_global_setting('payment_instructions', request.form.get('payment_instructions', ''))
            db.set_global_setting('pilot_notice_text', request.form.get('pilot_notice_text', ''))
            db.set_global_setting('show_pilot_notice', '1' if request.form.get('show_pilot_notice') == '1' else '0')
            flash('Správa prodeje uložena', 'success')
        elif action == 'save_pricing':
            pricing_ok = True
            try:
                raw = request.form.get('pricing_tarifs_json', '')
                if raw.strip():
                    tarifs = json.loads(raw)
                    if isinstance(tarifs, dict):
                        db.set_global_setting('pricing_tarifs', tarifs)
            except (json.JSONDecodeError, TypeError):
                flash('Neplatný JSON u ceníku – uložení přeskočeno', 'error')
                pricing_ok = False
            trial = request.form.get('trial_limit_total_files', '')
            if trial.strip():
                try:
                    db.set_global_setting('trial_limit_total_files', int(trial))
                except ValueError:
                    pass
            if pricing_ok:
                flash('Ceny a tarify uloženy', 'success')
        elif action == 'save_marketing':
            for key in ('landing_hero_title', 'landing_hero_subtitle', 'landing_hero_badge', 'landing_cta_primary', 'landing_cta_secondary',
                        'landing_section_how_title', 'landing_section_modes_title', 'landing_mode_agent_title', 'landing_mode_agent_text',
                        'landing_mode_cloud_title', 'landing_mode_cloud_text', 'landing_tarif_basic_desc', 'landing_tarif_standard_desc', 'landing_tarif_premium_desc'):
                db.set_global_setting(key, request.form.get(key, ''))
            for json_key, form_key in (('landing_how_steps', 'landing_how_steps_json'), ('landing_faq', 'landing_faq_json'),
                                       ('testimonials', 'testimonials_json'), ('partner_logos', 'partner_logos_json')):
                raw = request.form.get(form_key, '')
                if raw.strip():
                    try:
                        val = json.loads(raw)
                        db.set_global_setting(json_key, val)
                    except (json.JSONDecodeError, TypeError):
                        pass
            for json_key, form_key in (('top_promo_bar', 'top_promo_bar_json'), ('exit_intent_popup', 'exit_intent_popup_json')):
                raw = request.form.get(form_key, '')
                if raw.strip():
                    try:
                        val = json.loads(raw)
                        if isinstance(val, dict):
                            db.set_global_setting(json_key, val)
                    except (json.JSONDecodeError, TypeError):
                        pass
            flash('Marketing uložen', 'success')
        elif action == 'save_legal':
            for key in ('legal_vop_html', 'legal_gdpr_html', 'footer_disclaimer', 'app_legal_notice'):
                db.set_global_setting(key, request.form.get(key, ''))
            flash('Právní info uloženo', 'success')
        elif action == 'save_system':
            for key in ('seo_meta_title', 'seo_meta_description', 'email_order_confirmation_subject', 'email_order_confirmation_body',
                        'email_welcome_subject', 'email_welcome_body'):
                db.set_global_setting(key, request.form.get(key, ''))
            try:
                n = request.form.get('analysis_timeout_seconds', '')
                if n.strip():
                    db.set_global_setting('analysis_timeout_seconds', int(n))
            except ValueError:
                pass
            for json_key, form_key in (('header_scripts', 'header_scripts_json'), ('allowed_extensions', 'allowed_extensions_json')):
                raw = request.form.get(form_key, '')
                if raw.strip():
                    try:
                        val = json.loads(raw)
                        db.set_global_setting(json_key, val)
                    except (json.JSONDecodeError, TypeError):
                        pass
            flash('Systémové nastavení uloženo', 'success')
        return redirect(url_for('admin.settings'))

    st = _settings_for_admin(db)
    user = session.get('admin_user') or {}
    if not user.get('display_name'):
        user = dict(user)
        user['display_name'] = user.get('email') or 'Admin'
    # Pro textarea s JSON předáme řetězce
    def _json_str(val, default='[]'):
        if val is None:
            return default
        if isinstance(val, str):
            return val
        return json.dumps(val, ensure_ascii=False, indent=2)
    return render_template('admin_settings.html', user=user, active_page='settings',
                          maintenance_mode=st.get('maintenance_mode', False),
                          allow_new_registrations=st.get('allow_new_registrations', True),
                          settings=st,
                          pricing_tarifs_json=_json_str(st.get('pricing_tarifs'), '{}'),
                          landing_how_steps_json=_json_str(st.get('landing_how_steps')),
                          landing_faq_json=_json_str(st.get('landing_faq')),
                          testimonials_json=_json_str(st.get('testimonials')),
                          partner_logos_json=_json_str(st.get('partner_logos')),
                          top_promo_bar_json=_json_str(st.get('top_promo_bar'), '{}'),
                          exit_intent_popup_json=_json_str(st.get('exit_intent_popup'), '{}'),
                          header_scripts_json=_json_str(st.get('header_scripts')),
                          allowed_extensions_json=_json_str(st.get('allowed_extensions')))


# =============================================================================
# API ENDPOINTS PRO ADMIN AKCE
# =============================================================================

@admin_bp.route('/admin/api/trial/reset', methods=['POST'])
@admin_required
def api_trial_reset():
    """Vynuluje Trial počítadlo pro dané machine_id (umožní znovu vyzkoušet)."""
    db = get_db()
    machine_id = (request.form.get('machine_id') or '').strip()
    if not machine_id and request.is_json:
        try:
            data = request.get_json(silent=True) or {}
            machine_id = (data.get('machine_id') or '').strip()
        except Exception:
            pass
    if not machine_id:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Chybí machine_id'}), 400
        flash('Chybí machine_id', 'error')
        return redirect(url_for('admin.trial'))
    if db.reset_trial_usage(machine_id):
        flash(f'Trial vynulován pro zařízení {machine_id[:20]}…', 'success')
        if request.is_json:
            return jsonify({'success': True, 'message': 'Trial resetován'}), 200
        return redirect(url_for('admin.trial'))
    if request.is_json:
        return jsonify({'success': False, 'error': 'Zařízení nenalezeno nebo již vynulováno'}), 404
    flash('Zařízení nenalezeno nebo již vynulováno', 'error')
    return redirect(url_for('admin.trial'))


@admin_bp.route('/admin/api/tier/update', methods=['POST'])
@admin_required
def api_update_tier():
    """Aktualizuje globální tier (stránka /admin/tiers)."""
    db = get_db()
    try:
        tier_id = int(request.form.get('tier_id', 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Neplatné tier_id'}), 400
    name = request.form.get('name', '').strip()
    max_files_raw = request.form.get('max_files_limit', '').strip()
    try:
        max_files_limit = int(max_files_raw) if max_files_raw else None
    except (TypeError, ValueError):
        max_files_limit = None
    allow_signatures = request.form.get('allow_signatures') == '1'
    allow_timestamp = request.form.get('allow_timestamp') == '1'
    allow_excel_export = request.form.get('allow_excel_export') == '1'
    allow_advanced_filters = request.form.get('allow_advanced_filters') == '1'
    max_devices_raw = request.form.get('max_devices', '').strip()
    try:
        max_devices = int(max_devices_raw) if max_devices_raw else None
    except (TypeError, ValueError):
        max_devices = None
    daily_files_limit = None
    raw_daily = request.form.get('daily_files_limit', '').strip()
    if raw_daily:
        try:
            daily_files_limit = int(raw_daily)
        except ValueError:
            pass
    rate_limit_hour = None
    raw_rate = request.form.get('rate_limit_hour', '').strip()
    if raw_rate:
        try:
            rate_limit_hour = int(raw_rate)
        except ValueError:
            pass
    max_file_size_mb = None
    raw_size = request.form.get('max_file_size_mb', '').strip()
    if raw_size:
        try:
            max_file_size_mb = int(raw_size)
        except ValueError:
            pass

    if not tier_id:
        return jsonify({'success': False, 'error': 'Chybí tier_id'}), 400

    ok = db.update_tier(
        tier_id,
        name=name or None,
        max_files_limit=max_files_limit,
        allow_signatures=allow_signatures,
        allow_timestamp=allow_timestamp,
        allow_excel_export=allow_excel_export,
        allow_advanced_filters=allow_advanced_filters,
        max_devices=max_devices,
        daily_files_limit=daily_files_limit,
        rate_limit_hour=rate_limit_hour,
        max_file_size_mb=max_file_size_mb,
    )
    if ok:
        return jsonify({'success': True, 'message': 'Tier aktualizován'})
    return jsonify({'success': False, 'error': 'Tier nenalezen'}), 404


@admin_bp.route('/admin/api/activity')
@admin_required
def api_activity():
    """JSON pro Chart.js: aktivita (soubory) za období. Query: from=YYYY-MM-DD, to=YYYY-MM-DD."""
    db = get_db()
    date_from = request.args.get('from', '').strip() or None
    date_to = request.args.get('to', '').strip() or None
    if date_from or date_to:
        data = db.get_activity_for_period(date_from=date_from, date_to=date_to)
    else:
        data = db.get_activity_last_30_days()
    return jsonify({'success': True, 'data': data})


@admin_bp.route('/admin/api/stats/kpis')
@admin_required
def api_stats_kpis():
    """KPI: obrat, aktivní licence Free/Paid, chybovost."""
    db = get_db()
    kpis = db.get_dashboard_kpis()
    return jsonify({'success': True, 'data': kpis})


@admin_bp.route('/admin/api/stats/users-ranking')
@admin_required
def api_stats_users_ranking():
    """Nejaktivnější uživatelé (počet souborů)."""
    db = get_db()
    limit = min(20, max(5, int(request.args.get('limit', 10))))
    data = db.get_user_activity_ranking(limit=limit)
    return jsonify({'success': True, 'data': data})


@admin_bp.route('/admin/api/stats/trial')
@admin_required
def api_stats_trial():
    """Statistiky Trialu: unikátní Machine-ID, celkem souborů, top."""
    db = get_db()
    data = db.get_trial_stats()
    return jsonify({'success': True, 'data': data})


@admin_bp.route('/admin/api/users-by-tier')
@admin_required
def api_users_by_tier():
    """JSON pro Doughnut: počet uživatelů podle tieru."""
    db = get_db()
    licenses = db.admin_get_all_licenses()
    tiers_list = db.get_all_license_tiers()
    by_tier = {t['name']: 0 for t in tiers_list}
    for l in licenses:
        tn = l.get('tier_name') or 'Free'
        by_tier[tn] = by_tier.get(tn, 0) + 1
    return jsonify({'success': True, 'data': by_tier})


@admin_bp.route('/admin/api/license/create', methods=['POST'])
@admin_required
def api_create_license():
    """Vytvoří novou licenci. tier_id z dropdown (DB tier) má přednost před tier 0–3."""
    db = get_db()

    user_name = request.form.get('user_name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip() or None
    tier_id_raw = request.form.get('tier_id', '').strip()
    try:
        tier_id = int(tier_id_raw) if tier_id_raw else None
    except (TypeError, ValueError):
        tier_id = None
    try:
        tier = int(request.form.get('tier', 0))
    except (TypeError, ValueError):
        tier = 0
    tier = max(0, min(3, tier))
    try:
        days = int(request.form.get('days', 365))
    except (TypeError, ValueError):
        days = 365

    if not user_name or not email:
        return jsonify({'success': False, 'error': 'Vyplňte jméno a email'}), 400

    existing = db.get_license_by_email(email)
    if existing:
        return jsonify({
            'success': False,
            'error': 'Tento e-mail už je použit u jiné aktivní licence. Zvolte jiný e-mail.'
        }), 400

    if tier_id is not None:
        tier_row = db.get_tier_by_id(tier_id)
        if tier_row and (tier_row.get('name') or '').strip() == 'Trial' and request.form.get('days') in (None, '', '365'):
            days = 7  # Trial: výchozí 7 dní
        api_key = db.admin_create_license_by_tier_id(user_name, email, tier_id, days=days, password=password)
    else:
        api_key = db.admin_generate_license_key(user_name, email, tier, days, password=password)

    if api_key:
        return jsonify({
            'success': True,
            'api_key': api_key,
            'message': f'Licence vytvořena pro {email}'
        })
    return jsonify({'success': False, 'error': 'Chyba při vytváření licence'}), 500


@admin_bp.route('/admin/api/license/update', methods=['POST'])
@admin_required
def api_update_license():
    """Aktualizuje licenci: tier, jméno, email, expirace, status, platební údaje, heslo, feature flags."""
    db = get_db()

    api_key = request.form.get('api_key', '').strip()
    tier_id_raw = request.form.get('tier_id', '').strip()
    try:
        tier_id = int(tier_id_raw) if tier_id_raw else None
    except (TypeError, ValueError):
        tier_id = None

    # Pouze Tier (dropdown)
    if tier_id is not None and not request.form.get('days') and not request.form.get('new_password') and not request.form.get('user_name') and not request.form.get('email'):
        if not api_key:
            return jsonify({'success': False, 'error': 'Chybí API klíč'}), 400
        old_lic = db.get_user_license(api_key)
        if db.admin_set_user_tier(api_key, tier_id):
            if old_lic:
                db.insert_payment_log(api_key, 'změna_tarifu', details=f"Tier -> {tier_id}")
            return jsonify({'success': True, 'message': 'Tarif uživatele aktualizován'})
        return jsonify({'success': False, 'error': 'Licence nenalezena'}), 404

    # Rozšířená aktualizace
    user_name = request.form.get('user_name', '').strip() or None
    email = request.form.get('email', '').strip() or None
    license_expires = request.form.get('license_expires', '').strip() or None
    if not license_expires and request.form.get('days'):
        try:
            from datetime import datetime, timedelta
            days = int(request.form.get('days'))
            license_expires = (datetime.now() + timedelta(days=days)).isoformat()[:10]
        except (TypeError, ValueError):
            pass
    is_active_raw = request.form.get('is_active')
    is_active = None if is_active_raw is None or is_active_raw == '' else (is_active_raw in ('1', 'true', 'ano'))
    payment_method = request.form.get('payment_method', '').strip() or None
    last_payment_date = request.form.get('last_payment_date', '').strip() or None
    new_password = request.form.get('new_password', '').strip() or None
    max_batch_size_raw = request.form.get('max_batch_size', '').strip()
    try:
        max_batch_size = int(max_batch_size_raw) if max_batch_size_raw else None
    except (TypeError, ValueError):
        max_batch_size = None
    allow_signatures = request.form.get('allow_signatures') == '1'
    allow_timestamp = request.form.get('allow_timestamp') == '1'
    allow_excel_export = request.form.get('allow_excel_export') == '1'
    max_devices_raw = request.form.get('max_devices', '').strip()
    try:
        max_devices = int(max_devices_raw) if max_devices_raw else None
    except (TypeError, ValueError):
        max_devices = None
    try:
        tier = int(request.form.get('tier', 0))
    except (TypeError, ValueError):
        tier = 0
    tier = max(0, min(3, tier))

    if not api_key:
        return jsonify({'success': False, 'error': 'Chybí API klíč'}), 400

    db.admin_update_user_full(
        api_key,
        user_name=user_name,
        email=email,
        license_expires=license_expires,
        is_active=is_active,
        payment_method=payment_method,
        last_payment_date=last_payment_date,
    )
    if tier_id is not None:
        db.admin_set_user_tier(api_key, tier_id)
        db.insert_payment_log(api_key, 'změna_tarifu', details=f"Tier ID {tier_id}")
    if request.form.get('days'):
        license_days = int(request.form.get('days'))
        db.update_license_tier(api_key, tier, license_days)
    if new_password:
        db.admin_set_license_password(api_key, new_password)
    db.admin_update_license_features(
        api_key,
        max_batch_size=max_batch_size,
        allow_signatures=allow_signatures,
        allow_timestamp=allow_timestamp,
        allow_excel_export=allow_excel_export,
        max_devices=max_devices,
    )

    return jsonify({'success': True, 'message': 'Licence aktualizována'})


@admin_bp.route('/admin/api/license/welcome-package', methods=['POST'])
@admin_required
def api_welcome_package():
    """Vygeneruje náhodné heslo, nastaví ho v DB a vrátí text e-mailu pro uvítací balíček."""
    import secrets
    import string
    db = get_db()
    api_key = (request.form.get('api_key') or '').strip()
    if not api_key and request.is_json:
        api_key = (request.get_json(silent=True) or {}).get('api_key', '')
    api_key = (api_key or '').strip()
    if not api_key:
        return jsonify({'success': False, 'error': 'Chybí api_key'}), 400
    lic = db.get_user_license(api_key)
    if not lic:
        return jsonify({'success': False, 'error': 'Licence nenalezena'}), 404
    email = lic.get('email') or ''
    tier_name = lic.get('tier_name') or 'Standard'
    # Generovat náhodné heslo (8 znaků: písmena + číslice)
    alphabet = string.ascii_letters + string.digits
    new_password = ''.join(secrets.choice(alphabet) for _ in range(10))
    db.admin_set_license_password(api_key, new_password)
    # Odkaz na stažení – vždy na aktuální doménu (PA)
    base_url = request.host_url.rstrip('/') if request else ''
    if not base_url:
        base_url = 'https://cieslar.pythonanywhere.com'
    download_url = base_url + '/download'
    email_body = (
        f"Váš účet: {email}\n"
        f"Heslo: {new_password}\n"
        f"Licence: {tier_name}\n"
        f"API Klíč: {api_key}\n"
        f"Odkaz na stažení: {download_url}\n"
    )
    return jsonify({
        'success': True,
        'password': new_password,
        'email_body': email_body,
        'email': email,
        'tier_name': tier_name,
        'api_key': api_key,
        'download_url': download_url,
    })


@admin_bp.route('/admin/api/license/set-password', methods=['POST'])
@admin_required
def api_set_license_password():
    """Nastaví nebo změní heslo pro přihlášení uživatele v agentovi (e-mail + heslo)."""
    db = get_db()

    api_key = request.form.get('api_key', '').strip()
    new_password = request.form.get('new_password', '').strip()
    new_password2 = request.form.get('new_password2', '').strip()

    if not api_key:
        return jsonify({'success': False, 'error': 'Chybí API klíč'}), 400
    if not new_password:
        return jsonify({'success': False, 'error': 'Zadejte nové heslo'}), 400
    if new_password != new_password2:
        return jsonify({'success': False, 'error': 'Hesla se neshodují'}), 400
    if len(new_password) < 6:
        return jsonify({'success': False, 'error': 'Heslo musí mít alespoň 6 znaků'}), 400

    success = db.admin_set_license_password(api_key, new_password)

    if success:
        return jsonify({'success': True, 'message': 'Heslo uživatele bylo změněno'})
    else:
        return jsonify({'success': False, 'error': 'Licence nenalezena'}), 404


@admin_bp.route('/admin/api/license/billing')
@admin_required
def api_license_billing_list():
    """Historie fakturace pro uživatele (api_key v query)."""
    db = get_db()
    api_key = request.args.get('api_key', '').strip()
    if not api_key:
        return jsonify({'success': False, 'error': 'Chybí api_key'}), 400
    rows = db.get_billing_history(api_key, limit=100)
    return jsonify({'success': True, 'data': rows})


@admin_bp.route('/admin/api/license/billing', methods=['POST'])
@admin_required
def api_license_billing_add():
    """Přidá záznam do historie fakturace."""
    db = get_db()
    api_key = request.form.get('api_key', '').strip()
    description = request.form.get('description', '').strip() or None
    amount_cents = request.form.get('amount_cents', '').strip()
    try:
        amount_cents = int(amount_cents) if amount_cents else None
    except (TypeError, ValueError):
        amount_cents = None
    paid_at = request.form.get('paid_at', '').strip() or None
    if not api_key:
        return jsonify({'success': False, 'error': 'Chybí api_key'}), 400
    db.add_billing_record(api_key, description=description, amount_cents=amount_cents, paid_at=paid_at)
    db.admin_update_user_full(api_key, last_payment_date=paid_at)
    db.insert_payment_log(api_key, 'fakturace', details=description or str(amount_cents))
    return jsonify({'success': True, 'message': 'Záznam přidán'})


@admin_bp.route('/admin/api/license/toggle', methods=['POST'])
@admin_required
def api_toggle_license():
    """Aktivuje/deaktivuje licenci"""
    db = get_db()

    api_key = request.form.get('api_key', '').strip()
    is_active = request.form.get('is_active', '1') == '1'

    if not api_key:
        return jsonify({'success': False, 'error': 'Chybí API klíč'}), 400

    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE api_keys SET is_active = ? WHERE api_key = ?
    ''', (is_active, api_key))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    if success:
        status = 'aktivována' if is_active else 'deaktivována'
        return jsonify({'success': True, 'message': f'Licence {status}'})
    else:
        return jsonify({'success': False, 'error': 'Licence nenalezena'}), 404


@admin_bp.route('/admin/api/license/reset-devices', methods=['POST'])
@admin_required
def api_reset_devices():
    """Resetuje zařízení pro licenci"""
    db = get_db()

    api_key = request.form.get('api_key', '').strip()

    if not api_key:
        return jsonify({'success': False, 'error': 'Chybí API klíč'}), 400

    deleted = db.admin_reset_devices(api_key)

    return jsonify({
        'success': True,
        'message': f'Odstraněno {deleted} zařízení'
    })


@admin_bp.route('/admin/api/license/delete', methods=['POST'])
@admin_required
def api_delete_license():
    """Smaže licenci"""
    db = get_db()

    api_key = request.form.get('api_key', '').strip()

    if not api_key:
        return jsonify({'success': False, 'error': 'Chybí API klíč'}), 400

    success = db.admin_delete_license(api_key)

    if success:
        return jsonify({'success': True, 'message': 'Licence smazána'})
    else:
        return jsonify({'success': False, 'error': 'Chyba při mazání'}), 500


@admin_bp.route('/admin/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Změna hesla přihlášeného admina."""
    if request.method == 'POST':
        current = request.form.get('current_password', '')
        new_pass = request.form.get('new_password', '')
        new_pass2 = request.form.get('new_password2', '')

        if not current or not new_pass or not new_pass2:
            flash('Vyplňte všechna pole', 'error')
            return redirect(url_for('admin.change_password'))

        if new_pass != new_pass2:
            flash('Nové heslo a potvrzení se neshodují', 'error')
            return redirect(url_for('admin.change_password'))

        if len(new_pass) < 6:
            flash('Nové heslo musí mít alespoň 6 znaků', 'error')
            return redirect(url_for('admin.change_password'))

        db = get_db()
        email = session.get('admin_user', {}).get('email')
        ok, msg = db.verify_admin_login(email, current)
        if not ok:
            flash('Aktuální heslo není správné', 'error')
            return redirect(url_for('admin.change_password'))

        user_id = session.get('admin_user', {}).get('id')
        if db.update_admin_user(user_id, password=new_pass):
            flash('Heslo bylo změněno', 'success')
            return redirect(url_for('admin.dashboard'))
        flash('Nepodařilo se změnit heslo', 'error')

    return render_template('admin_change_password.html', user=session.get('admin_user'))


@admin_bp.route('/admin/api/git-pull', methods=['POST'])
@admin_required
def api_git_pull():
    """Na serveru spustí git pull (a volitelně PA Reload). Pouze pro přihlášeného admina."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log = []
    try:
        r = subprocess.run(
            ['git', 'pull'],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = (r.stdout or '').strip() or (r.stderr or '').strip() or str(r.returncode)
        log.append(f"git pull: {out}")
        if r.returncode != 0:
            return jsonify({'success': False, 'log': log}), 500
    except Exception as e:
        log.append(f"Chyba: {e}")
        return jsonify({'success': False, 'log': log}), 500
    # Volitelně PA Reload
    try:
        username = os.environ.get('PA_USERNAME', '')
        api_token = os.environ.get('PA_API_TOKEN', '')
        domain = os.environ.get('PA_DOMAIN', '')
        if username and api_token and domain:
            import urllib.request
            url = f'https://www.pythonanywhere.com/api/v0/user/{username}/webapps/{domain}/reload/'
            req = urllib.request.Request(url, data=b'', headers={'Authorization': f'Token {api_token}'}, method='POST')
            with urllib.request.urlopen(req, timeout=30) as resp:
                log.append('Reload OK' if resp.status == 200 else f'Reload status {resp.status}')
        else:
            log.append('Reload preskočen (není nastaven PA_USERNAME/PA_API_TOKEN/PA_DOMAIN)')
    except Exception as e:
        log.append(f'Reload chyba: {e}')
    return jsonify({'success': True, 'log': log})


@admin_bp.route('/admin/api/license/<api_key>/devices', methods=['GET'])
@admin_required
def api_get_devices(api_key):
    """Vrátí seznam zařízení pro licenci"""
    db = get_db()

    devices = db.get_active_devices(api_key)

    return jsonify({
        'success': True,
        'devices': devices
    })


# =============================================================================
# SETUP ROUTE - pro vytvoření prvního admin účtu
# =============================================================================

@admin_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    """
    Setup stránka pro vytvoření prvního admin účtu

    Tato stránka je dostupná pouze pokud neexistuje žádný admin
    """
    db = get_db()

    # Zkontroluj jestli už existuje admin
    admins = db.get_all_admin_users()
    admin_exists = any(u['role'] == 'ADMIN' for u in admins)

    if admin_exists:
        flash('Admin účet už existuje. Přihlaste se.', 'info')
        return redirect(url_for('admin.login'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        if not email or not password:
            flash('Vyplňte email a heslo', 'error')
            return render_template('admin_setup.html')

        if password != password2:
            flash('Hesla se neshodují', 'error')
            return render_template('admin_setup.html')

        if len(password) < 6:
            flash('Heslo musí mít alespoň 6 znaků', 'error')
            return render_template('admin_setup.html')

        success, msg = db.create_admin_user(email, password, 'ADMIN', 'Administrator')

        if success:
            flash('Admin účet vytvořen! Nyní se můžete přihlásit.', 'success')
            return redirect(url_for('admin.login'))
        else:
            flash(f'Chyba: {msg}', 'error')

    return render_template('admin_setup.html')


# =============================================================================
# INICIALIZACE TESTOVACÍCH DAT
# =============================================================================

def init_test_data():
    """
    Inicializuje testovací data

    Volej tuto funkci pro vytvoření testovacích účtů:
    - admin@admin.cz / admin (výchozí přístup k dashboardu – viz ensure_default_admin)
    - tester-basic@test.cz / test123 / BASIC license
    - tester-pro@test.cz / test123 / PRO license
    """
    db = get_db()

    # Výchozí admin pro dashboard: admin@admin.cz / admin
    ensure_default_admin()
    print("Admin (dashboard): admin@admin.cz / admin")

    # Vytvoř testovací licence
    # Basic tester
    api_key_basic = db.admin_generate_license_key(
        user_name='Tester Basic',
        email='tester-basic@test.cz',
        tier=LicenseTier.BASIC,
        days=365
    )
    print(f"Basic license: {api_key_basic}")

    # Pro tester
    api_key_pro = db.admin_generate_license_key(
        user_name='Tester Pro',
        email='tester-pro@test.cz',
        tier=LicenseTier.PRO,
        days=365
    )
    print(f"Pro license: {api_key_pro}")

    # Enterprise tester (pro admina)
    api_key_ent = db.admin_generate_license_key(
        user_name='Admin Enterprise',
        email='admin@pdfcheck.cz',
        tier=LicenseTier.ENTERPRISE,
        days=365
    )
    print(f"Enterprise license: {api_key_ent}")

    return {
        'admin_email': 'admin@pdfcheck.cz',
        'admin_password': 'admin123',
        'basic_key': api_key_basic,
        'pro_key': api_key_pro,
        'enterprise_key': api_key_ent
    }


# Pro přímé spuštění (testování)
if __name__ == '__main__':
    print("Initializing test data...")
    result = init_test_data()
    print("\n=== Test Data Created ===")
    print(f"Admin: {result['admin_email']} / {result['admin_password']}")
    print(f"Basic API Key: {result['basic_key']}")
    print(f"Pro API Key: {result['pro_key']}")
    print(f"Enterprise API Key: {result['enterprise_key']}")
