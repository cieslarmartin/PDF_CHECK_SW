# settings_loader.py
# Centrální fallbacky pro global_settings. Všechna čtení přes tyto hodnoty, aby web/agent nespadly při prázdné DB.

import json
import os

# Výchozí hodnoty pro string / int / bool klíče (fallback když v DB nic není)
DEFAULTS = {
    # Globální přepínače (čtené jako bool v get_global_setting)
    "maintenance_mode": False,
    "allow_new_registrations": True,
    # Základní nastavení
    "provider_name": "Ing. Martin Cieślar",
    "provider_address": "Porubská 1, 742 83 Klimkovice – Václavovice",
    "provider_ico": "04830661",
    "provider_legal_note": "Fyzická osoba zapsaná v živnostenském rejstříku od 22. 2. 2016.",
    "contact_email": "",
    "contact_phone": "",
    "bank_account": "",
    "bank_iban": "",
    # Ceny a Tarify (čísla)
    "trial_limit_total_files": 10,
    # Landing – hero a CTA
    "landing_hero_title": "DokuCheck – Dokumentace bez chyb pro Portál stavebníka",
    "landing_hero_subtitle": "Rychlá kontrola PDF/PDF-A, podpisy a souladu dokumentů během minut.",
    "landing_hero_badge": "ONLINE + Desktop",
    "landing_cta_primary": "Vyzkoušet ONLINE Check",
    "landing_cta_secondary": "Stáhnout aplikaci zdarma",
    "landing_section_how_title": "Jak to funguje",
    "landing_section_modes_title": "Dva režimy: Z Agenta vs Cloud",
    "landing_mode_agent_title": "Z Agenta",
    "landing_mode_agent_text": "Soubory na disku, na server jen metadata.",
    "landing_mode_cloud_title": "Cloud",
    "landing_mode_cloud_text": "Celé PDF na server. Rychlé vyzkoušení.",
    "landing_tarif_basic_desc": "Ideální pro otestování v pilotním provozu.",
    "landing_tarif_standard_desc": "Plné funkce, export, historie.",
    "landing_tarif_premium_desc": "Na míru pro větší týmy.",
    # Právní – krátké texty (dlouhé VOP/GDPR mají fallback v šabloně nebo prázdné = zobraz šablonu)
    "footer_disclaimer": "Výsledky mají informativní charakter a nenahrazují Portál stavebníka. Autor neručí za správnost.",
    "app_legal_notice": "Výsledky kontroly mají pouze informativní charakter a nenahrazují Portál stavebníka.",
    # Systém – SEO, e-maily, Agent
    "seo_meta_title": "DokuCheck – Dokumentace bez chyb | Portál stavebníka",
    "seo_meta_description": "Rychlá kontrola PDF/PDF-A, podpisy a souladu dokumentů pro Portál stavebníka.",
    "analysis_timeout_seconds": 300,
    "email_order_confirmation_subject": "DokuCheck – potvrzení objednávky č. {order_id}",
    "email_order_confirmation_body": "",
    "email_welcome_subject": "Vítejte v DokuCheck",
    "email_welcome_body": "",
    # Upozornění na webu (pilotní provoz, SmartScreen)
    "pilot_notice_text": "Aplikace je v pilotním provozu.\nHláška systému SmartScreen je očekávaná (aplikace prochází certifikací).",
    "show_pilot_notice": True,
}

# Výchozí hodnoty pro JSON klíče
DEFAULT_PRICING_TARIFS = {
    "basic": {"label": "BASIC", "amount_czk": 1290},
    "standard": {"label": "PRO", "amount_czk": 1990},
}

DEFAULT_LANDING_HOW_STEPS = [
    {"title": "Nahraj / vyber složku", "text": "Přetáhněte PDF nebo vyberte složku s dokumenty."},
    {"title": "Proveď kontrolu", "text": "Automatická kontrola PDF/A, podpisy a časových razítek."},
    {"title": "Exportuj výsledky", "text": "Výstupy do CSV/Excel, přehled podle složek."},
]

DEFAULT_LANDING_FAQ = [
    {"q": "Co kontroluje DokuCheck?", "a": "PDF/A-3, elektronické podpisy, časová razítka a soulad s Portálem stavebníka."},
    {"q": "Jaký je rozdíl mezi Z Agenta a Cloud?", "a": "Z Agenta: soubory na disku, na server jen metadata. Cloud: celé PDF na server (demo)."},
    {"q": "Mohu zrušit předplatné?", "a": "Ano, předplatné se neobnoví po ukončení období."},
    {"q": "Kde najdu Můj účet?", "a": "Portál – historie a nastavení."},
]

DEFAULT_TOP_PROMO_BAR = {"text": "", "background_color": "#1e5a8a", "is_active": False}

DEFAULT_EXIT_INTENT_POPUP = {"title": "", "body": "", "button_text": "Zavřít", "is_active": False}

DEFAULT_ALLOWED_EXTENSIONS = [".pdf"]

DEFAULT_HEADER_SCRIPTS = []


def get_setting(db, key: str):
    """Vrátí hodnotu klíče z DB s fallbackem na výchozí. db = instance Database()."""
    if key in DEFAULTS:
        default = DEFAULTS[key]
        if isinstance(default, bool):
            return db.get_setting_bool(key, default)
        if isinstance(default, int):
            return db.get_setting_int(key, default)
        return db.get_global_setting(key, default)
    if key == "pricing_tarifs":
        return db.get_setting_json(key, DEFAULT_PRICING_TARIFS)
    if key == "landing_how_steps":
        return db.get_setting_json(key, DEFAULT_LANDING_HOW_STEPS)
    if key == "landing_faq":
        return db.get_setting_json(key, DEFAULT_LANDING_FAQ)
    if key == "testimonials":
        return db.get_setting_json(key, [])
    if key == "partner_logos":
        return db.get_setting_json(key, [])
    if key == "top_promo_bar":
        return db.get_setting_json(key, DEFAULT_TOP_PROMO_BAR)
    if key == "exit_intent_popup":
        return db.get_setting_json(key, DEFAULT_EXIT_INTENT_POPUP)
    if key == "header_scripts":
        return db.get_setting_json(key, DEFAULT_HEADER_SCRIPTS)
    if key == "allowed_extensions":
        return db.get_setting_json(key, DEFAULT_ALLOWED_EXTENSIONS)
    return db.get_global_setting(key, "")


def load_settings_for_views(db):
    """
    Načte všechna nastavení potřebná pro veřejné view (landing, checkout, VOP, GDPR, footer).
    Vrací slovník: vždy platné hodnoty (fallback pokud DB prázdná).
    """
    out = {}
    for k in DEFAULTS:
        if isinstance(DEFAULTS[k], bool):
            out[k] = db.get_setting_bool(k, DEFAULTS[k])
        elif isinstance(DEFAULTS[k], int):
            out[k] = db.get_setting_int(k, DEFAULTS[k])
        elif isinstance(DEFAULTS[k], bool):
            out[k] = db.get_setting_bool(k, DEFAULTS[k])
        else:
            out[k] = db.get_global_setting(k, DEFAULTS[k]) or DEFAULTS[k]
    out["pricing_tarifs"] = db.get_setting_json("pricing_tarifs", DEFAULT_PRICING_TARIFS)
    out["landing_how_steps"] = db.get_setting_json("landing_how_steps", DEFAULT_LANDING_HOW_STEPS)
    out["landing_faq"] = db.get_setting_json("landing_faq", DEFAULT_LANDING_FAQ)
    out["testimonials"] = db.get_setting_json("testimonials", [])
    out["partner_logos"] = db.get_setting_json("partner_logos", [])
    out["top_promo_bar"] = db.get_setting_json("top_promo_bar", DEFAULT_TOP_PROMO_BAR)
    out["exit_intent_popup"] = db.get_setting_json("exit_intent_popup", DEFAULT_EXIT_INTENT_POPUP)
    out["header_scripts"] = db.get_setting_json("header_scripts", [])
    out["legal_vop_html"] = db.get_global_setting("legal_vop_html", "")
    out["legal_gdpr_html"] = db.get_global_setting("legal_gdpr_html", "")
    out["download_url"] = db.get_global_setting("download_url", "") or ""
    out["pilot_notice_text"] = db.get_global_setting("pilot_notice_text", DEFAULTS.get("pilot_notice_text", "")) or DEFAULTS.get("pilot_notice_text", "")
    out["show_pilot_notice"] = db.get_setting_bool("show_pilot_notice", DEFAULTS.get("show_pilot_notice", True))
    # Sekce Připravujeme (Coming Soon) na hlavní stránce
    out["coming_soon_intro"] = db.get_global_setting("coming_soon_intro", "") or "Rozšíření Agenta, která řeší reálné potřeby projektantů: kontrola cest a názvů souborů a úpravy PDF včetně podepisování přímo v systému."
    out["coming_soon_path_title"] = db.get_global_setting("coming_soon_path_title", "") or "Path Checker"
    out["coming_soon_path_subtitle"] = db.get_global_setting("coming_soon_path_subtitle", "") or "Aplikace pro kontrolu cest, revizi a logistiku souborů"
    out["coming_soon_path_items"] = db.get_global_setting("coming_soon_path_items", "") or "Kontrola délky názvů a cest (Path Length) na vašem PC – prevence problémů na OneDrive/SharePoint\nBlesková kontrola tisíců souborů najednou\nExport problematických souborů do Excelu pro rychlou opravu"
    out["coming_soon_path_benefit"] = db.get_global_setting("coming_soon_path_benefit", "") or "→ Žádné neočekávané pády u velkých zakázek. Z Agenta – vše běží na vašem PC."
    out["coming_soon_editor_title"] = db.get_global_setting("coming_soon_editor_title", "") or "Online editor a podpis PDF"
    out["coming_soon_editor_subtitle"] = db.get_global_setting("coming_soon_editor_subtitle", "") or "Úprava PDF dokumentů, vkládání podpisů a digitální schvalování přímo v systému"
    out["coming_soon_editor_items"] = db.get_global_setting("coming_soon_editor_items", "") or "Odstranění starých podpisů a razítek, hromadný převod do PDF/A-3a\nNové podepsání autorizačním razítkem v jednom kroku\nSnadná oprava nevyhovujících PDF pro Portál stavebníka"
    out["coming_soon_editor_benefit"] = db.get_global_setting("coming_soon_editor_benefit", "") or "→ Méně vrácení dokumentace, rychlejší odeslání na portál. Z Agenta – soubory na disku."
    # Seznamy odrážek pro šablonu (řádky rozdělené \n)
    path_items = (out.get("coming_soon_path_items") or "").split("\n")
    out["coming_soon_path_items_list"] = [x.strip() for x in path_items if x.strip()]
    editor_items = (out.get("coming_soon_editor_items") or "").split("\n")
    out["coming_soon_editor_items_list"] = [x.strip() for x in editor_items if x.strip()]
    try:
        from version import WEB_VERSION
        out["web_version"] = WEB_VERSION
    except ImportError:
        out["web_version"] = "w26.02.001"
    return out


def get_trial_limit_total_files(db) -> int:
    """Trial – max. souborů na zařízení. Pro api_endpoint a database."""
    return db.get_setting_int("trial_limit_total_files", 10)


def get_pricing_tarifs(db):
    """Ceník tarifů: { basic: {label, amount_czk}, ... }. Jediný zdroj: DB (Admin Nastavení → Ceny)."""
    return db.get_setting_json("pricing_tarifs", DEFAULT_PRICING_TARIFS)


def get_email_order_confirmation_subject(db) -> str:
    return db.get_global_setting("email_order_confirmation_subject", DEFAULTS["email_order_confirmation_subject"]) or DEFAULTS["email_order_confirmation_subject"]


def get_allowed_extensions(db):
    """Povolené přípony pro agenta. Pro API odpověď agentovi."""
    return db.get_setting_json("allowed_extensions", DEFAULT_ALLOWED_EXTENSIONS)


def get_analysis_timeout_seconds(db) -> int:
    """Maximální čas analýzy v sekundách. Pro API odpověď agentovi."""
    return db.get_setting_int("analysis_timeout_seconds", 300)
