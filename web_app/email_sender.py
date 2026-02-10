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
        smtp_host = os.environ.get('MAIL_SERVER') or app.config.get('MAIL_SERVER', '') or 'smtp.seznam.cz'
        smtp_port = int(os.environ.get('MAIL_PORT') or app.config.get('MAIL_PORT') or 465)
        smtp_user = os.environ.get('MAIL_USERNAME') or app.config.get('MAIL_USERNAME', '') or 'info@dokucheck.cz'
        smtp_pass = os.environ.get('MAIL_PASSWORD') or app.config.get('MAIL_PASSWORD', '')
        if not smtp_host or not smtp_user:
            return False
        from_addr = app.config.get('MAIL_DEFAULT_SENDER') or smtp_user
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


ADMIN_INFO_EMAIL = os.environ.get('ADMIN_INFO_EMAIL', 'info@dokucheck.cz')


def send_order_notification_to_admin(order_id, jmeno_firma, tarif, amount_czk):
    """Odešle z info@dokucheck.cz na info@dokucheck.cz notifikaci o nové objednávce (UTF-8). Volá se po kliknutí na OBJEDNAT v adminu."""
    to_email = 'info@dokucheck.cz'
    subject = 'Nová objednávka: {}'.format(order_id)
    body = (
        'Jméno zákazníka: {}\n'
        'Tarif: {}\n'
        'Částka: {} Kč\n'
    ).format(jmeno_firma or '—', tarif or '—', amount_czk or '—')
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
    """Pošle informační e-mail administrátorovi na info@dokucheck.cz."""
    return send_email(ADMIN_INFO_EMAIL, subject, body_plain, append_footer=False)


def send_order_confirmation_email(order_id, email, jmeno_firma, tarif, amount_czk, db=None):
    """E-mail 1: potvrzení objednávky. Šablona z site_config (placeholdery: jmeno, cena, vs), na konec footer."""
    templates = get_email_templates()
    subject_tpl = templates.get("order_confirmation_subject") or "DokuCheck – potvrzení objednávky č. {vs}"
    body_tpl = templates.get("order_confirmation_body") or (
        "Děkujeme za objednávku DokuCheck PRO.\n\nPro aktivaci zašlete {cena} Kč na účet (VS: {vs})."
    )
    subject = subject_tpl.replace("{vs}", str(order_id)).replace("{cena}", str(amount_czk)).replace("{jmeno}", str(jmeno_firma or ""))
    body = body_tpl.replace("{vs}", str(order_id)).replace("{cena}", str(amount_czk)).replace("{jmeno}", str(jmeno_firma or ""))
    return send_email(email, subject, body, append_footer=True)


def send_activation_email(user_email, password_plain, download_url=None, login_url=None, user_name=None):
    """E-mail 2: aktivace. Šablona z DB (placeholdery: {jmeno}, {email}, {heslo}, {login_url}, {download_url}). Při password_plain=None se {heslo} nahradí textem o stávajícím hesle."""
    if not download_url:
        download_url = os.environ.get('DOWNLOAD_URL', 'https://www.dokucheck.cz/download')
    if not login_url:
        login_url = 'https://www.dokucheck.cz/portal'
    jmeno_text = (user_name or user_email or '').strip() or user_email or ''
    heslo_text = (password_plain if (password_plain is not None and str(password_plain).strip()) else
                 'Vaše stávající heslo (použijte heslo z předchozí aktivace).')
    templates = get_email_templates()
    subject_tpl = templates.get("activation_subject") or "DokuCheck PRO – přístup aktivní"
    body_tpl = templates.get("activation_body") or (
        "Dobrý den, {jmeno}!\n\nVaše platba byla přijata. Přístup k DokuCheck PRO je aktivní.\n\n"
        "Přihlašovací jméno (e-mail): {email}\nHeslo: {heslo}\n\n"
        "Odkaz na přihlášení: {login_url}\n\nStahujte aplikaci zde: {download_url}"
    )
    def repl(t):
        return (t.replace("{jmeno}", jmeno_text).replace("{email}", user_email or '')
                .replace("{heslo}", heslo_text).replace("{download_url}", download_url or '').replace("{login_url}", login_url or ''))
    subject = repl(subject_tpl)
    body = repl(body_tpl)
    return send_email(user_email, subject, body, append_footer=True)
