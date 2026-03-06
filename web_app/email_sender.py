# email_sender.py – odesílání e-mailů (objednávky, aktivace)
# Načítá šablony ze site_config.json, nahrazuje placeholdery, připojuje footer_text.

import os
from flask import current_app

try:
    from site_config_loader import get_email_templates
except ImportError:
    def get_email_templates():
        return {}


def _apply_footer(body_plain, footer_text):
    """Připojí patičku k tělu e-mailu."""
    if not (footer_text and str(footer_text).strip()):
        return body_plain
    return (body_plain.rstrip() + "\n\n" + str(footer_text).strip()).strip()


def send_email(to_email, subject, body_plain, append_footer=True):
    """Odešle e-mail (UTF-8). Pokud append_footer=True, na konec přidá footer_text ze šablon."""
    if append_footer:
        templates = get_email_templates()
        body_plain = _apply_footer(body_plain, templates.get("footer_text", ""))
    app = current_app
    try:
        mail = getattr(app, 'mail', None)
        if mail:
            from flask_mail import Message
            msg = Message(subject=subject, recipients=[to_email], body=body_plain)
            mail.send(msg)
            return True
        import smtplib
        from email.message import EmailMessage
        from email.policy import SMTPUTF8
        # UTF-8: send_message(msg) + set_content(..., charset='utf-8') – odstraní chybu 'ascii' codec (ý, í, ě)
        smtp_host = os.environ.get('MAIL_SERVER') or app.config.get('MAIL_SERVER', '') or 'smtp.seznam.cz'
        smtp_port = int(os.environ.get('MAIL_PORT') or app.config.get('MAIL_PORT') or 465)
        smtp_user = os.environ.get('MAIL_USERNAME') or app.config.get('MAIL_USERNAME', '') or 'info@dokucheck.cz'
        smtp_pass = os.environ.get('MAIL_PASSWORD') or app.config.get('MAIL_PASSWORD', '')
        if not smtp_host or not smtp_user:
            return False
        from_addr = app.config.get('MAIL_DEFAULT_SENDER') or smtp_user
        # Ekvivalent MIMEText(body_plain, 'plain', 'utf-8') + server.send_message(msg) – pojistka proti 'ascii' codec (ě, č, ř, ý)
        msg = EmailMessage(policy=SMTPUTF8)
        msg['Subject'] = subject
        msg['From'] = from_addr if from_addr else smtp_user
        msg['To'] = to_email
        msg.set_content(body_plain, subtype='plain', charset='utf-8')
        use_ssl = app.config.get('MAIL_USE_SSL', True)
        if use_ssl and smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                if smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_port == 587:
                    server.starttls()
                if smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        return True
    except Exception as e:
        import traceback
        err_str = str(e)
        print('[SMTP] Odeslání e-mailu se nezdařilo:', err_str)
        print('[SMTP] Traceback:\n' + traceback.format_exc())
        if '530' in err_str or '535' in err_str:
            msg = "SMTP CHYBA: Zkontrolujte Heslo pro aplikace ve WSGI!"
            print('[SMTP]', msg)
            if app and hasattr(app, 'logger'):
                app.logger.warning(msg)
        if app and hasattr(app, 'logger'):
            app.logger.warning("Odeslání e-mailu se nezdařilo: %s", e)
        return False


def _order_notification_email():
    """Příjemce notifikací objednávek: z app.config (nastavení v dashboardu) nebo z env."""
    app = current_app
    return app.config.get('ORDER_NOTIFICATION_EMAIL') or os.environ.get('ORDER_NOTIFICATION_EMAIL', 'objednavky@dokucheck.cz')


def _admin_info_email():
    """Příjemce ostatních admin mailů: z app.config nebo z env."""
    app = current_app
    return app.config.get('ADMIN_INFO_EMAIL') or os.environ.get('ADMIN_INFO_EMAIL', 'info@dokucheck.cz')


def send_order_notification_to_admin(order=None, **kwargs):
    """Odešle notifikaci o nové objednávce na adresu z Nastavení → E-maily (order_notification_email).
    Přijímá slovník objednávky (order) s poli: order_display_number, jmeno_firma, ico, email, tarif,
    ulice, mesto, psc, dic, discount_requested, amount_czk, amount_czk_final, created_at, status.
    Tělo e-mailu obsahuje všechny údaje od klienta."""
    if order is None:
        order = kwargs
    order_number = order.get('order_display_number') or order.get('invoice_number') or order.get('id') or '—'
    to_email = _order_notification_email()
    subject = 'Nová objednávka: {}'.format(order_number)
    lines = [
        'Nová objednávka',
        '',
        'Číslo objednávky: {}'.format(order_number),
        'Jméno / Firma: {}'.format(order.get('jmeno_firma') or '—'),
        'IČO: {}'.format(order.get('ico') or '—'),
        'E-mail: {}'.format(order.get('email') or '—'),
        'Tarif: {}'.format(order.get('tarif') or '—'),
        'Ulice: {}'.format(order.get('ulice') or '—'),
        'Město: {}'.format(order.get('mesto') or '—'),
        'PSČ: {}'.format(order.get('psc') or '—'),
        'DIČ: {}'.format(order.get('dic') or '—'),
        'Požadavek na slevu: {}'.format('Ano' if order.get('discount_requested') else 'Ne'),
        'Částka (Kč): {}'.format(order.get('amount_czk') if order.get('amount_czk') is not None else '—'),
        'Částka po slevě (Kč): {}'.format(order.get('amount_czk_final') if order.get('amount_czk_final') is not None else '—'),
        'Datum: {}'.format(order.get('created_at') or '—'),
        'Status: {}'.format(order.get('status') or '—'),
    ]
    body = '\n'.join(lines)
    return send_email(to_email, subject, body, append_footer=False)


def send_email_with_attachment(to_email, subject, body_plain, attachment_path=None, attachment_filename=None, append_footer=True):
    """Odešle e-mail s volitelnou přílohou (PDF faktura)."""
    if append_footer:
        templates = get_email_templates()
        body_plain = _apply_footer(body_plain, templates.get("footer_text", ""))
    app = current_app
    try:
        mail = getattr(app, 'mail', None)
        if mail:
            from flask_mail import Message
            msg = Message(subject=subject, recipients=[to_email], body=body_plain)
            if attachment_path and os.path.isfile(attachment_path):
                with open(attachment_path, 'rb') as f:
                    msg.attach(attachment_filename or os.path.basename(attachment_path), 'application/pdf', f.read())
            mail.send(msg)
            return True
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        from email import encoders
        smtp_host = os.environ.get('MAIL_SERVER') or app.config.get('MAIL_SERVER', '') or 'smtp.seznam.cz'
        smtp_port = int(os.environ.get('MAIL_PORT') or app.config.get('MAIL_PORT') or 465)
        smtp_user = os.environ.get('MAIL_USERNAME') or app.config.get('MAIL_USERNAME', '') or 'info@dokucheck.cz'
        smtp_pass = os.environ.get('MAIL_PASSWORD') or app.config.get('MAIL_PASSWORD', '')
        if not smtp_host or not smtp_user:
            return False
        msg = MIMEMultipart()
        msg['Subject'] = subject
        from_addr = app.config.get('MAIL_DEFAULT_SENDER') or smtp_user
        msg['From'] = from_addr if from_addr else smtp_user
        msg['To'] = to_email
        msg.attach(MIMEText(body_plain, 'plain', 'utf-8'))
        if attachment_path and os.path.isfile(attachment_path):
            with open(attachment_path, 'rb') as f:
                part = MIMEBase('application', 'pdf')
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment', filename=(attachment_filename or os.path.basename(attachment_path)))
            msg.attach(part)
        use_ssl = app.config.get('MAIL_USE_SSL', True)
        if use_ssl and smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                if smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_port == 587:
                    server.starttls()
                if smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to_email], msg.as_string())
        return True
    except Exception as e:
        import traceback
        err_str = str(e)
        print('[SMTP] Odeslání e-mailu s přílohou se nezdařilo:', err_str)
        print('[SMTP] Traceback:\n' + traceback.format_exc())
        if '530' in err_str or '535' in err_str:
            msg = "SMTP CHYBA: Zkontrolujte Heslo pro aplikace ve WSGI!"
            print('[SMTP]', msg)
            if app and hasattr(app, 'logger'):
                app.logger.warning(msg)
        if app and hasattr(app, 'logger'):
            app.logger.warning("Odeslání e-mailu se nezdařilo: %s", e)
        return False


def notify_admin(subject, body_plain):
    """Pošle informační e-mail administrátorovi na adresu z Nastavení → E-maily (admin_info_email)."""
    return send_email(_admin_info_email(), subject, body_plain, append_footer=False)


def send_order_confirmation_email(order_id, email, jmeno_firma, tarif, amount_czk, db=None):
    """E-mail 1: potvrzení objednávky. Šablona z site_config (placeholdery: jmeno, cena, vs), na konec footer."""
    templates = get_email_templates()
    subject_tpl = templates.get("order_confirmation_subject") or "DokuCheck – potvrzení objednávky č. {vs}"
    body_tpl = templates.get("order_confirmation_body") or (
        "Děkujeme za objednávku DokuCheck.\n\nPro aktivaci zašlete {cena} Kč na účet (VS: {vs})."
    )
    subject = subject_tpl.replace("{vs}", str(order_id)).replace("{cena}", str(amount_czk)).replace("{jmeno}", str(jmeno_firma or ""))
    body = body_tpl.replace("{vs}", str(order_id)).replace("{cena}", str(amount_czk)).replace("{jmeno}", str(jmeno_firma or ""))
    return send_email(email, subject, body, append_footer=True)


def send_activation_email(user_email, password_plain=None, download_url=None, login_url=None, user_name=None, set_password_url=None):
    """E-mail 2: aktivace. Bez hesla v těle (antispam): při set_password_url se pošle jen odkaz na nastavení hesla.
    Placeholdery: {jmeno}, {email}, {heslo}, {login_url}, {download_url}, {set_password_url}.
    - set_password_url je nastaven: tělo obsahuje odkaz na nastavení hesla, heslo se do e-mailu neposílá.
    - set_password_url není nastaven, password_plain je: staré chování (heslo v mailu – může jít do spamu).
    - set_password_url ani password_plain: prodloužení přístupu, text o stávajícím hesle."""
    if not download_url:
        download_url = os.environ.get('DOWNLOAD_URL', 'https://www.dokucheck.cz/download')
    if not login_url:
        login_url = 'https://www.dokucheck.cz/portal'
    jmeno_text = (user_name or user_email or '').strip() or user_email or ''
    templates = get_email_templates()
    subject_tpl = templates.get("activation_subject") or "DokuCheck – přístup aktivní"

    if set_password_url:
        # Nový režim: žádné heslo v e-mailu, jen odkaz na nastavení hesla (menší riziko spamu)
        body_tpl = templates.get("activation_body") or (
            "Dobrý den, {jmeno}!\n\nVaše platba byla přijata. Přístup k DokuCheck je aktivní.\n\n"
            "Přihlašovací jméno (e-mail): {email}\n\n"
            "Pro dokončení aktivace si nastavte heslo kliknutím na odkaz:\n{set_password_url}\n\n"
            "Po nastavení hesla se přihlaste zde: {login_url}\n\nStahujte aplikaci zde: {download_url}"
        )
        heslo_text = ""  # do těla se nedává
    elif password_plain and str(password_plain).strip():
        # Zpětná kompatibilita: heslo v mailu (může jít do spamu)
        body_tpl = templates.get("activation_body") or (
            "Dobrý den, {jmeno}!\n\nVaše platba byla přijata. Přístup k DokuCheck je aktivní.\n\n"
            "Přihlašovací jméno (e-mail): {email}\nHeslo: {heslo}\n\n"
            "Odkaz na přihlášení: {login_url}\n\nStahujte aplikaci zde: {download_url}"
        )
        heslo_text = password_plain.strip()
    else:
        # Prodloužení: uživatel má heslo, jen připomínka
        body_tpl = templates.get("activation_body") or (
            "Dobrý den, {jmeno}!\n\nPřístup k DokuCheck byl prodloužen.\n\n"
            "Přihlaste se stávajícím heslem zde: {login_url}\n\nStahujte aplikaci: {download_url}"
        )
        heslo_text = "Vaše stávající heslo (použijte heslo z předchozí aktivace)."

    set_pwd_url_placeholder = (set_password_url or "").strip()

    def repl(t):
        return (t.replace("{jmeno}", jmeno_text).replace("{email}", user_email or '')
                .replace("{heslo}", heslo_text).replace("{download_url}", download_url or '')
                .replace("{login_url}", login_url or '').replace("{set_password_url}", set_pwd_url_placeholder))
    subject = repl(subject_tpl)
    body = repl(body_tpl)
    return send_email(user_email, subject, body, append_footer=True)
