# settings_loader.py
# Centrální fallbacky pro global_settings. Všechna čtení přes tyto hodnoty, aby web/agent nespadly při prázdné DB.

import json
import logging
import os

logger = logging.getLogger(__name__)

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

# Přehled aktualizací pro landing – sekce „Co je nového“ (měsíc, název, odrážky).
DEFAULT_LANDING_UPDATES = [
    {
        "month": "03/2026",
        "title": "Březen 2026",
        "items": [
            "Implementováno automatické rozlišování certifikačních autorit v ČR (PostSignum, I.CA, eIdentity) a podpora pro vícenásobné podpisy v PDF.",
        ],
    },
    {
        "month": "02/2026",
        "title": "Únor 2026",
        "items": [
            "Funkce pro čtení a zamykání souborů podle metodiky MMR pro digitální stavební řízení.",
        ],
    },
]


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
    # Sekce Připravujeme (Coming Soon) na hlavní stránce – dynamický seznam karet z JSON nebo z 4 starých klíčů
    out["coming_soon_intro"] = db.get_global_setting("coming_soon_intro", "") or "Rozšíření Agenta, která řeší reálné potřeby projektantů: kontrola cest a názvů souborů a úpravy PDF včetně podepisování přímo v systému."
    cards_json = db.get_setting_json("coming_soon_cards", None)
    if isinstance(cards_json, list) and len(cards_json) > 0:
        out["coming_soon_cards"] = []
        for c in cards_json:
            item = dict(c) if isinstance(c, dict) else {}
            items_str = item.get("items") or ""
            if isinstance(items_str, list):
                item["items_list"] = [x.strip() for x in items_str if str(x).strip()]
            else:
                item["items_list"] = [x.strip() for x in str(items_str).split("\n") if x.strip()]
            item.setdefault("color", "blue")
            out["coming_soon_cards"].append(item)
    else:
        # Zpětná kompatibilita: sestavit z 4 pevných klíčů
        _def = lambda k, d: (db.get_global_setting(k, "") or "").strip() or d
        out["coming_soon_cards"] = [
            {"title": _def("coming_soon_path_title", "Path Checker"), "subtitle": _def("coming_soon_path_subtitle", "Aplikace pro kontrolu cest, revizi a logistiku souborů"), "items": _def("coming_soon_path_items", ""), "benefit": _def("coming_soon_path_benefit", "→ Žádné neočekávané pády u velkých zakázek. Z Agenta – vše běží na vašem PC."), "items_list": [x.strip() for x in (_def("coming_soon_path_items", "") or "").split("\n") if x.strip()], "color": "blue"},
            {"title": _def("coming_soon_editor_title", "Online editor a podpis PDF"), "subtitle": _def("coming_soon_editor_subtitle", "Úprava PDF dokumentů, vkládání podpisů a digitální schvalování přímo v systému"), "items": _def("coming_soon_editor_items", ""), "benefit": _def("coming_soon_editor_benefit", "→ Méně vrácení dokumentace, rychlejší odeslání na portál. Z Agenta – soubory na disku."), "items_list": [x.strip() for x in (_def("coming_soon_editor_items", "") or "").split("\n") if x.strip()], "color": "purple"},
            {"title": _def("coming_soon_zpf_title", "Výpočet poplatku za odvody ze ZPF"), "subtitle": _def("coming_soon_zpf_subtitle", "Program pro výpočet poplatku za odvody ze ZPF"), "items": _def("coming_soon_zpf_items", ""), "benefit": _def("coming_soon_zpf_benefit", "→ Rychlý výpočet poplatků pro projekty."), "items_list": [x.strip() for x in (_def("coming_soon_zpf_items", "") or "").split("\n") if x.strip()], "color": "green"},
            {"title": _def("coming_soon_parking_title", "Výpočet počtu parkovacích míst"), "subtitle": _def("coming_soon_parking_subtitle", "Aplikace pro výpočet počtu parkovacích míst do projektu"), "items": _def("coming_soon_parking_items", ""), "benefit": _def("coming_soon_parking_benefit", "→ Správný počet parkovacích míst do projektu na první pokus."), "items_list": [x.strip() for x in (_def("coming_soon_parking_items", "") or "").split("\n") if x.strip()], "color": "amber"},
        ]
    out["landing_updates"] = db.get_setting_json("landing_updates", DEFAULT_LANDING_UPDATES)
    if not isinstance(out["landing_updates"], list):
        out["landing_updates"] = list(DEFAULT_LANDING_UPDATES)
    out["download_whats_new"] = db.get_global_setting("download_whats_new", "") or ""
    try:
        from version import WEB_VERSION, WEB_BUILD, AGENT_BUILD_ID, AGENT_VERSION_DISPLAY
        out["web_version"] = (WEB_VERSION or "").strip() or "w26.02.001"
        out["web_build"] = str(WEB_BUILD) if WEB_BUILD is not None else "n/a"
        out["agent_build_id"] = str(AGENT_BUILD_ID) if AGENT_BUILD_ID is not None else "51"
        out["agent_version_display"] = (AGENT_VERSION_DISPLAY or "").strip() or "v26.03.0xx"
        out["agent_version"] = out["agent_version_display"]
        out["agent_build"] = out["agent_build_id"]
    except (ImportError, AttributeError) as e:
        logger.warning("version.py nedostupný, použit fallback: %s", e)
        out["web_version"] = "w26.02.001"
        out["web_build"] = "n/a"
        out["agent_build_id"] = "51"
        out["agent_version_display"] = "v26.03.0xx"
        out["agent_version"] = out["agent_version_display"]
        out["agent_build"] = out["agent_build_id"]
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
