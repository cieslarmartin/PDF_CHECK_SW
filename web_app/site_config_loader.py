# site_config_loader.py – načtení a uložení site_config.json (email_templates, pricing_tarifs)

import json
import os

SITE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'site_config.json')

DEFAULT_EMAIL_TEMPLATES = {
    "footer_text": "---\nDokuCheck – Dokumentace bez chyb | www.dokucheck.cz\nTato zpráva byla odeslána automaticky.",
    "order_confirmation_subject": "DokuCheck – potvrzení objednávky č. {vs}",
    "order_confirmation_body": "Dobrý den,\n\nDěkujeme za objednávku DokuCheck PRO.\n\nPro aktivaci zašlete {cena} Kč na účet uvedený v patičce, variabilní symbol: {vs}.\n\nJméno / Firma: {jmeno}",
    "activation_subject": "DokuCheck PRO – přístup aktivní",
    "activation_body": "Vaše platba byla přijata!\n\nPřístup k DokuCheck PRO je aktivní.\n\nPřihlašovací e-mail: {email}\nHeslo: {heslo}\n\nStahujte aplikaci zde: {download_url}",
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
    """Vrátí slovník email_templates (footer_text, order_confirmation_*, activation_*)."""
    config = load_site_config()
    templates = config.get("email_templates") or {}
    out = dict(DEFAULT_EMAIL_TEMPLATES)
    for k in out:
        if k in templates and templates[k] is not None:
            out[k] = str(templates[k])
    return out


def save_email_templates(templates):
    """Uloží email_templates do site_config.json (sloučí s existujícím obsahem)."""
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
