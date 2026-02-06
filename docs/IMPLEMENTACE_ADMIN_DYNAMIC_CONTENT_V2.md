# Implementace Admin-Managed Dynamic Content (V2)

## Výstup před zahájením kódování

Dokument obsahuje:
1. Finální schéma tabulky `global_settings` (SQLite + varianta PostgreSQL/Supabase).
2. Kompletní seznam všech klíčů editovatelných v Adminu (včetně rozšíření V2).
3. Potvrzení mechanismu Fallbacků.

---

## 1. Finální schéma tabulky `global_settings`

### 1.1 Stávající stav (SQLite) – zachovat kompatibilitu

Aplikace používá **SQLite**. Tabulka zůstane **key/value**; hodnoty včetně JSON se ukládají jako TEXT.

```sql
-- SQLite (stávající + doplnění pro migraci)
CREATE TABLE IF NOT EXISTS global_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

-- Volitelný sloupec pro logické seskupení v Admin UI (migrace _migrate_schema):
-- ALTER TABLE global_settings ADD COLUMN category TEXT DEFAULT 'general';
-- Kde category IN ('basic', 'pricing', 'marketing', 'legal', 'system', 'agent')
```

**Pravidlo:** `value` je vždy řetězec. Čísla a boolean ukládáme jako `"123"`, `"1"`/`"0"`. JSON jako serializovaný řetězec. Při čtení v kódu: `get_global_setting(key, default)` vrací `default`, pokud řádek chybí nebo je `value` prázdný; typová konverze a parsování JSON probíhá v aplikační vrstvě (helper s fallbackem).

### 1.2 Varianta PostgreSQL / Supabase (pro budoucí migraci)

Pokud budete chtít přejít na PostgreSQL/Supabase, stejná logika s jedinou tabulkou:

```sql
CREATE TABLE IF NOT EXISTS global_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index pro filtrování podle kategorie (pokud přidáte sloupec category)
-- CREATE INDEX IF NOT EXISTS idx_global_settings_category ON global_settings(category);
```

V SQLite lze přidat `updated_at` v migraci (SQLite podporuje DEFAULT CURRENT_TIMESTAMP).

### 1.3 Rozhodnutí

- **Neměnit** stávající strukturu `(key, value)` – žádné další povinné sloupce.
- **Kategorizace** pro Admin záložky: řešit v kódu pomocí konstanty `SETTINGS_KEYS_BY_CATEGORY` (mapování key → záložka), ne nutně sloupcem v DB.
- **Všechny nové položky** (včetně V2) = nové klíče v téže tabulce; hodnoty typu objekt/pole = JSON string v `value`.

---

## 2. Kompletní seznam klíčů editovatelných v Adminu

Níže jsou **všechny klíče** pro `global_settings`. Každý má v kódu definovaný **fallback** (výchozí hodnotu), aby web a agent nespadly při prázdné DB nebo prázdné hodnotě.

### 2.1 Záložka: Základní nastavení (Identita provozovatele, Banka)

| Klíč | Typ | Popis | Fallback (výchozí) |
|------|-----|--------|---------------------|
| `provider_name` | string | Jméno / firma provozovatele | `"Ing. Martin Cieślar"` |
| `provider_address` | string | Sídlo (jedno pole) | `"Porubská 1, 742 83 Klimkovice – Václavovice"` |
| `provider_ico` | string | IČO | `"04830661"` |
| `provider_legal_note` | string | Právní doplněk (např. FO v ŽR od …) | `"Fyzická osoba zapsaná v živnostenském rejstříku od 22. 2. 2016."` |
| `contact_email` | string | Kontaktní e-mail | `"info@dokucheck.app"` |
| `bank_account` | string | Číslo účtu (pro platby) | `""` |
| `bank_iban` | string | IBAN | `""` |
| `maintenance_mode` | bool | Údržba (Maintenance Mode) | `false` |
| `allow_new_registrations` | bool | Povolit nové registrace | `true` |

### 2.2 Záložka: Ceny a Tarify

| Klíč | Typ | Popis | Fallback (výchozí) |
|------|-----|--------|---------------------|
| `pricing_tarifs` | JSON | Tarify: `{"basic":{"label":"BASIC","amount_czk":990},"standard":{...},"premium":{...}}` | `{"basic":{"label":"BASIC","amount_czk":990},"standard":{"label":"STANDARD","amount_czk":1990},"premium":{"label":"PREMIUM","amount_czk":4990}}` |
| `trial_limit_total_files` | int | Trial – max. souborů na zařízení | `10` |

*(Limity per tier: zůstávají v tabulce `license_tiers` – sloupce `daily_files_limit`, `rate_limit_hour`, `max_file_size_mb` – ne v global_settings.)*

### 2.3 Záložka: Marketing (Hero, FAQ, Reference, Promo)

| Klíč | Typ | Popis | Fallback (výchozí) |
|------|-----|--------|---------------------|
| `landing_hero_title` | string | Hero nadpis | `"DokuCheck – Dokumentace bez chyb pro Portál stavebníka"` |
| `landing_hero_subtitle` | string | Hero podnadpis | `"Rychlá kontrola PDF/PDF-A, podpisy a souladu dokumentů během minut."` |
| `landing_hero_badge` | string | Badge text | `"ONLINE + Desktop"` |
| `landing_cta_primary` | string | Text primárního CTA | `"Vyzkoušet ONLINE Check"` |
| `landing_cta_secondary` | string | Text sekundárního CTA | `"Stáhnout aplikaci zdarma"` |
| `landing_section_how_title` | string | Nadpis „Jak to funguje“ | `"Jak to funguje"` |
| `landing_how_steps` | JSON | Kroky: `[{"title":"...","text":"..."}, ...]` (3 kroky) | Pole z aktuální šablony |
| `landing_section_modes_title` | string | Nadpis „Dva režimy“ | `"Dva režimy: Z Agenta vs Cloud"` |
| `landing_mode_agent_title` | string | Režim Z Agenta – nadpis | `"Z Agenta"` |
| `landing_mode_agent_text` | string | Režim Z Agenta – popis | `"Soubory na disku, na server jen metadata."` |
| `landing_mode_cloud_title` | string | Režim Cloud – nadpis | `"Cloud"` |
| `landing_mode_cloud_text` | string | Režim Cloud – popis | `"Celé PDF na server. Rychlé vyzkoušení."` |
| `landing_tarif_basic_desc` | string | Popis tarifu Basic na landingu | `"Pro menší objemy."` |
| `landing_tarif_standard_desc` | string | Popis tarifu Standard/Pro | `"Plné funkce, export, historie."` |
| `landing_tarif_premium_desc` | string | Popis tarifu Premium/Firemní | `"Na míru pro větší týmy."` |
| `landing_faq` | JSON | FAQ: `[{"q":"...","a":"..."}, ...]` | Pole z aktuální šablony |
| **Marketing & Social Proof (V2)** | | | |
| `testimonials` | JSON | Reference: `[{"name":"...","position":"...","text":"...","photo_url":"..."}, ...]` | `[]` |
| `partner_logos` | JSON | Loga partnerů: `["https://...", ...]` (pole URL) | `[]` |
| **Konverzní prvky (V2)** | | | |
| `top_promo_bar` | JSON | Promo lišta: `{"text":"...","background_color":"#...","is_active":true}` | `{"text":"","background_color":"#1e5a8a","is_active":false}` |
| `exit_intent_popup` | JSON | Exit intent popup: `{"title":"...","body":"...","button_text":"...","is_active":false}` | `{"title":"","body":"","button_text":"Zavřít","is_active":false}` |

### 2.4 Záložka: Právní info (VOP, GDPR, disclaimery)

| Klíč | Typ | Popis | Fallback (výchozí) |
|------|-----|--------|---------------------|
| `legal_vop_html` | string (HTML) | Celý obsah stránky VOP | Obsah šablony `vop.html` (nebo prázdné → zobrazit šablonu) |
| `legal_gdpr_html` | string (HTML) | Celý obsah stránky GDPR | Obsah šablony `gdpr.html` (nebo prázdné → šablona) |
| `footer_disclaimer` | string | Právní upozornění v patičce webu | Stávající string z kódu |
| `app_legal_notice` | string | Disclaimer v aplikaci (Agent) | Stávající string z kódu |

### 2.5 Záložka: Systém (SEO, Skripty, Timeouty, Agent, E-maily)

| Klíč | Typ | Popis | Fallback (výchozí) |
|------|-----|--------|---------------------|
| **SEO & Tracking (V2)** | | | |
| `seo_meta_title` | string | Meta title hlavní landing page | `"DokuCheck – Dokumentace bez chyb \| Portál stavebníka"` |
| `seo_meta_description` | string | Meta description hlavní landing | `"Rychlá kontrola PDF/PDF-A, podpisy a souladu dokumentů pro Portál stavebníka."` |
| `header_scripts` | JSON | Skripty do `<head>`: `["<script>...</script>", ...]` (pole HTML řetězců) | `[]` |
| **Deep Agent Settings (V2)** | | | |
| `allowed_extensions` | JSON | Povolené přípony: `[".pdf", ".zip", ".dwg"]` | `[".pdf"]` |
| `analysis_timeout_seconds` | int | Maximální čas analýzy (sekundy) – agent nahlásí timeout | `300` (5 min) |
| **Dynamické E-maily (V2)** | | | |
| `email_order_confirmation_subject` | string | Předmět e-mailu po objednávce; placeholders: `{name}`, `{order_id}`, `{tarif}`, `{amount_czk}` | `"DokuCheck – potvrzení objednávky č. {order_id}"` |
| `email_order_confirmation_body` | string (text/HTML) | Tělo e-mailu; placeholders: `{name}`, `{order_id}`, `{tarif}`, `{amount_czk}`, `{bank_note}`, `{link}` | Stávající tělo z kódu (např. _send_order_confirmation_email) |
| `email_welcome_subject` | string | Předmět uvítacího e-mailu (volitelně) | `"Vítejte v DokuCheck"` |
| `email_welcome_body` | string | Tělo uvítacího e-mailu; placeholders: `{name}`, `{link}` | `""` |

---

## 3. Shrnutí klíčů podle záložek Admin UI

- **Základní nastavení:**  
  `provider_name`, `provider_address`, `provider_ico`, `provider_legal_note`, `contact_email`, `bank_account`, `bank_iban`, `maintenance_mode`, `allow_new_registrations`

- **Ceny a Tarify:**  
  `pricing_tarifs`, `trial_limit_total_files`

- **Marketing:**  
  `landing_hero_*`, `landing_how_steps`, `landing_section_modes_*`, `landing_mode_agent_*`, `landing_mode_cloud_*`, `landing_tarif_*_desc`, `landing_faq`, `testimonials`, `partner_logos`, `top_promo_bar`, `exit_intent_popup`

- **Právní info:**  
  `legal_vop_html`, `legal_gdpr_html`, `footer_disclaimer`, `app_legal_notice`

- **Systém:**  
  `seo_meta_title`, `seo_meta_description`, `header_scripts`, `allowed_extensions`, `analysis_timeout_seconds`, `email_order_confirmation_subject`, `email_order_confirmation_body`, `email_welcome_subject`, `email_welcome_body`

*(Tier limity zůstávají v tabulce `license_tiers`: `daily_files_limit`, `rate_limit_hour`, `max_file_size_mb` – editace v existující stránce Tier definice.)*

---

## 4. Mechanismus Fallbacků – potvrzení

- **Pravidlo:** Žádné místo v kódu nesmí spoléhat na to, že v `global_settings` existuje konkrétní klíč nebo že hodnota je vyplněná.
- **Čtení:** Vždy použít `db.get_global_setting(key, default)`. Pokud řádek chybí nebo je `value` prázdný řetězec, metoda vrátí `default`. Stávající `get_global_setting` již vrací `default` při chybějícím řádku; je nutné explicitně ošetřit i prázdný řetězec (`if not val and val != '0': return default` pro string, nebo pro boolean vrátit default při `val not in ('1','0','true','false',...)`).
- **Typová konverze:** Zavedeme pomocné funkce (např. v modulu `settings_loader` nebo rozšíření `database`):
  - `get_setting_int(key, default)` – parsuje int; při chybě nebo prázdné hodnotě vrátí default.
  - `get_setting_bool(key, default)` – již částečně v `get_global_setting` (1/0, true/false); sjednotit a vždy vrátit bool.
  - `get_setting_json(key, default)` – `json.loads(value)`; při výjimce nebo null vrátí `default`. Fallback musí být vždy validní struktura (např. `[]`, `{}`).
- **Šablony:** View předává do šablony proměnné (např. `provider_name`, `landing_hero_title`). Pokud je hodnota z DB prázdná, view předá fallback (načtený z konstanty nebo z výchozí šablony). Šablona tedy nikdy nedostane `None` nebo chybějící klíč pro kritické texty – vždy string nebo bezpečná výchozí hodnota.
- **Agent:** Logika Agenta se nemění. Tam, kde agent dnes používá konstantu (např. povolené přípony, timeout), bude volat API nebo konfiguraci načtenou ze serveru; server načte `allowed_extensions` a `analysis_timeout_seconds` z `global_settings` s fallbackem. Agent pouze dostane hodnoty v odpovědi (např. v `/api/license/info` nebo v dedikovaném endpointu „agent config“); pokud server vrátí výchozí hodnoty kvůli prázdné DB, agent funguje jako dnes.
- **E-maily:** Před odesláním se šablona e-mailu sestaví z `email_order_confirmation_subject` a `email_order_confirmation_body`; nahradí se placeholdery. Pokud hodnota chybí, použije se vestavěný default (stávající text z kódu).

Tím je zajištěno, že **web ani agent nespadnou při prázdné DB nebo nevyplněných nových klíčích** – vždy se použije definovaný fallback v kódu.

---

## 5. Další krok

Po schválení tohoto výstupu lze zahájit kódování: migrace (doplnění defaultů do `global_settings` dle výše), rozšíření `get_global_setting`/pomocné gettery, načítání v view a v API, Admin UI po záložkách dle bodu 3.
