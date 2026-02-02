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

# Import databáze
try:
    from database import Database, generate_api_key
except ImportError:
    Database = None

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
    """Dekorátor pro ověření přihlášení"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_user' not in session:
            flash('Prosím přihlaste se', 'warning')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Dekorátor pro ověření admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_user' not in session:
            flash('Prosím přihlaste se', 'warning')
            return redirect(url_for('admin.login'))
        if session.get('admin_user', {}).get('role') != 'ADMIN':
            flash('Nemáte oprávnění pro tuto akci', 'error')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function


# =============================================================================
# AUTH ROUTES
# =============================================================================

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Přihlašovací stránka"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Vyplňte email a heslo', 'error')
            return render_template('admin_login.html')

        db = get_db()
        success, result = db.verify_admin_login(email, password)

        if success:
            session['admin_user'] = result
            session.permanent = True
            flash(f'Vítejte, {result.get("display_name", email)}!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
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
    """Admin dashboard - správa licencí"""
    db = get_db()

    # Získej všechny licence
    licenses = db.admin_get_all_licenses()

    # Statistiky
    stats = {
        'total_licenses': len(licenses),
        'active_licenses': sum(1 for l in licenses if l['is_active'] and not l.get('is_expired')),
        'expired_licenses': sum(1 for l in licenses if l.get('is_expired')),
        'total_devices': sum(l.get('active_devices', 0) for l in licenses),
        'total_checks': sum(l.get('total_checks', 0) for l in licenses),
        'by_tier': {}
    }

    # Počet podle tierů
    for tier in LicenseTier:
        stats['by_tier'][tier.name] = sum(1 for l in licenses if l['license_tier'] == tier.value)

    # Data pro grafy (Chart.js)
    activity_30 = db.get_activity_last_30_days()
    tiers_list = db.get_all_license_tiers()
    by_tier_counts = {}
    for t in tiers_list:
        by_tier_counts[t['name']] = sum(1 for l in licenses if (l.get('tier_id') == t['id']) or (l.get('tier_name') == t['name']))
    for t in tiers_list:
        if t['name'] not in by_tier_counts:
            by_tier_counts[t['name']] = 0

    return render_template('admin_dashboard.html',
                          licenses=licenses,
                          stats=stats,
                          tiers=TIER_NAMES,
                          tiers_list=tiers_list or [],
                          activity_30=activity_30 or [],
                          by_tier_counts=by_tier_counts or {},
                          user=session.get('admin_user'))


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
    return render_template('admin_user_audit.html', logs=logs, user_id=user_id, user_email=user_email, user_display=user_display, user=session.get('admin_user'))


@admin_bp.route('/admin/tiers')
@admin_required
def tiers():
    """Globální definice tierů (Free, Basic, Pro, Enterprise) – pouze úprava limitů, ne per-user."""
    db = get_db()
    tiers_list = db.get_all_license_tiers()
    return render_template('admin_tiers.html', tiers_list=tiers_list or [], user=session.get('admin_user'))


@admin_bp.route('/admin/logs')
@admin_required
def logs():
    """Stránka logů (user_logs) s filtrem/vyhledáváním."""
    db = get_db()
    search = request.args.get('q', '').strip()
    page = max(1, int(request.args.get('page', 1)))
    per_page = 100
    offset = (page - 1) * per_page
    logs_list = db.get_user_logs(user_id=None, limit=per_page, offset=offset, search=search if search else None)
    return render_template('admin_logs.html', logs=logs_list, search=search, page=page, per_page=per_page, user=session.get('admin_user'))


@admin_bp.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    """Global Config: údržba, nové registrace, změna hesla admina."""
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
        return redirect(url_for('admin.settings'))

    maintenance = db.get_global_setting('maintenance_mode', False)
    allow_reg = db.get_global_setting('allow_new_registrations', True)
    return render_template('admin_settings.html', user=session.get('admin_user'),
                          maintenance_mode=maintenance, allow_new_registrations=allow_reg)


# =============================================================================
# API ENDPOINTS PRO ADMIN AKCE
# =============================================================================

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
    max_devices_raw = request.form.get('max_devices', '').strip()
    try:
        max_devices = int(max_devices_raw) if max_devices_raw else None
    except (TypeError, ValueError):
        max_devices = None

    if not tier_id:
        return jsonify({'success': False, 'error': 'Chybí tier_id'}), 400

    ok = db.update_tier(
        tier_id,
        name=name or None,
        max_files_limit=max_files_limit,
        allow_signatures=allow_signatures,
        allow_timestamp=allow_timestamp,
        allow_excel_export=allow_excel_export,
        max_devices=max_devices,
    )
    if ok:
        return jsonify({'success': True, 'message': 'Tier aktualizován'})
    return jsonify({'success': False, 'error': 'Tier nenalezen'}), 404


@admin_bp.route('/admin/api/activity')
@admin_required
def api_activity():
    """JSON pro Chart.js: aktivita (soubory) za posledních 30 dní."""
    db = get_db()
    data = db.get_activity_last_30_days()
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
    """Vytvoří novou licenci"""
    db = get_db()

    user_name = request.form.get('user_name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip() or None
    try:
        tier = int(request.form.get('tier', 0))
    except (TypeError, ValueError):
        tier = 0
    tier = max(0, min(3, tier))  # 0-3
    try:
        days = int(request.form.get('days', 365))
    except (TypeError, ValueError):
        days = 365

    if not user_name or not email:
        return jsonify({'success': False, 'error': 'Vyplňte jméno a email'}), 400

    # E-mail musí být unikátní – jeden e-mail = jedna aktivní licence (aby přihlášení fungovalo)
    existing = db.get_license_by_email(email)
    if existing:
        return jsonify({
            'success': False,
            'error': 'Tento e-mail už je použit u jiné aktivní licence. Zvolte jiný e-mail.'
        }), 400

    api_key = db.admin_generate_license_key(user_name, email, tier, days, password=password)

    if api_key:
        return jsonify({
            'success': True,
            'api_key': api_key,
            'message': f'Licence vytvořena pro {email}'
        })
    else:
        return jsonify({'success': False, 'error': 'Chyba při vytváření licence'}), 500


@admin_bp.route('/admin/api/license/update', methods=['POST'])
@admin_required
def api_update_license():
    """Aktualizuje licenci. Pokud je poslán pouze tier_id (dropdown Tier), nastaví jen tier. Jinak tier + expirace + heslo."""
    db = get_db()

    api_key = request.form.get('api_key', '').strip()
    tier_id_raw = request.form.get('tier_id', '').strip()
    try:
        tier_id = int(tier_id_raw) if tier_id_raw else None
    except (TypeError, ValueError):
        tier_id = None

    # Režim "pouze Tier" (dropdown v /admin/users): jen tier_id
    if tier_id is not None and not request.form.get('days') and not request.form.get('new_password'):
        if not api_key:
            return jsonify({'success': False, 'error': 'Chybí API klíč'}), 400
        if db.admin_set_user_tier(api_key, tier_id):
            return jsonify({'success': True, 'message': 'Tier uživatele aktualizován'})
        return jsonify({'success': False, 'error': 'Licence nenalezena'}), 404

    # Plná aktualizace (legacy / rozšířený formulář)
    try:
        tier = int(request.form.get('tier', 0))
    except (TypeError, ValueError):
        tier = 0
    tier = max(0, min(3, tier))
    days = request.form.get('days')
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

    if not api_key:
        return jsonify({'success': False, 'error': 'Chybí API klíč'}), 400

    license_days = int(days) if days and str(days).strip() else None
    success = db.update_license_tier(api_key, tier, license_days)
    if not success:
        return jsonify({'success': False, 'error': 'Licence nenalezena'}), 404

    if tier_id is not None:
        db.admin_set_user_tier(api_key, tier_id)
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
    - admin@pdfcheck.cz / admin123 / ADMIN
    - tester-basic@test.cz / test123 / BASIC license
    - tester-pro@test.cz / test123 / PRO license
    """
    db = get_db()

    # Vytvoř admin účet
    success, msg = db.create_admin_user(
        email='admin@pdfcheck.cz',
        password='admin123',
        role='ADMIN',
        display_name='Administrator'
    )
    print(f"Admin account: {success} - {msg}")

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
