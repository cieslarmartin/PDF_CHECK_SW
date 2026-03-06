# site_config_loader.py – načtení a uložení site_config.json (email_templates, pricing_tarifs)

import json
import os

SITE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'site_config.json')

DEFAULT_EMAIL_TEMPLATES = {
    "footer_text": "<div style=\"color:#6b7280; font-size:12px; margin-top:20px; border-top:1px solid #e5e7eb; padding-top:10px;\">DokuCheck – Dokumentace bez chyb | <a href=\"https://www.dokucheck.cz\" style=\"color:#1e5a8a;\">www.dokucheck.cz</a><br>Tato zpráva byla odeslána automaticky.</div>",
    "order_confirmation_subject": "DokuCheck – potvrzení objednávky č. {vs}",
    "order_confirmation_body": "<div style=\"font-family:sans-serif; color:#374151; line-height:1.5;\"><h2 style=\"color:#1e5a8a; margin-top:0;\">Děkujeme za objednávku</h2><p>Dobrý den,</p><p>pro aktivaci zašlete prosím <strong>{cena} Kč</strong> na náš účet. <br>Variabilní symbol: <strong>{vs}</strong></p><p>Platební údaje a fakturu najdete v příloze tohoto e-mailu.</p><p>Zákazník: {jmeno}</p></div>",
    "activation_subject": "DokuCheck – přístup aktivní",
    "activation_body": "<div style=\"font-family:sans-serif; color:#374151; line-height:1.5;\"><h2 style=\"color:#16A34A; margin-top:0;\">Vaše platba byla přijata!</h2><p>Dobrý den, {jmeno},</p><p>přístup k aplikaci DokuCheck je nyní aktivní.</p><p><strong>Přihlašovací e-mail:</strong> {email}</p><p><a href=\"{set_password_url}\" style=\"display:inline-block; padding:10px 20px; background:#1e5a8a; color:white; text-decoration:none; border-radius:5px; margin:10px 0; font-weight:bold;\">Nastavit heslo k účtu</a></p><p>Poté se můžete přihlásit do Portálu: <br><a href=\"{login_url}\" style=\"color:#1e5a8a;\">{login_url}</a></p><p>Desktop aplikaci pro Windows stáhnete zde: <br><a href=\"{download_url}\" style=\"color:#1e5a8a;\">{download_url}</a></p></div>",
}


def load_site_config():
    """Načte celý site_config.json. Při chybě vrátí dict s prázdnými sekcemi."""
    if not os.path.isfile(SITE_CONFIG_PATH):
        return {"email_templates": dict(DEFAULT_EMAIL_TEMPLATES)}
    try:
        with open(SITE_CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, IOError):
        return {"email_templates": dict(DEFAULT_EMAIL_TEMPLATES)}


def get_email_templates():
    """Vrátí slovník email_templates (footer_text, order_confirmation_*, activation_*). Načítá z DB, jinak z site_config.json, jinak výchozí z kódu."""
    try:
        from database import Database
        db = Database()
        db_templates = db.get_email_templates_dict()
        if any(db_templates.get(k) for k in ('order_confirmation_subject', 'order_confirmation_body', 'activation_subject', 'activation_body')):
            out = dict(DEFAULT_EMAIL_TEMPLATES)
            for k in out:
                if k in db_templates and db_templates[k] is not None:
                    out[k] = str(db_templates[k])
            return out
    except Exception:
        pass
    config = load_site_config()
    templates = config.get("email_templates") or {}
    out = dict(DEFAULT_EMAIL_TEMPLATES)
    for k in out:
        if k in templates and templates[k] is not None:
            out[k] = str(templates[k])
    return out


def save_email_templates(templates):
    """Uloží email_templates: nejdřív do DB (pokud je k dispozici), jinak do site_config.json."""
    if not templates:
        return False
    try:
        from database import Database
        db = Database()
        # order_confirmation
        db.set_email_template(
            'order_confirmation',
            templates.get('order_confirmation_subject', ''),
            templates.get('order_confirmation_body', '')
        )
        # activation
        db.set_email_template(
            'activation',
            templates.get('activation_subject', ''),
            templates.get('activation_body', '')
        )
        # footer_text (body only)
        db.set_email_template('footer_text', '', templates.get('footer_text', ''))
        return True
    except Exception:
        pass
    config = load_site_config()
    if "email_templates" not in config:
        config["email_templates"] = {}
    for k, v in (templates or {}).items():
        if k in DEFAULT_EMAIL_TEMPLATES:
            config["email_templates"][k] = v
    try:
        with open(SITE_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False
