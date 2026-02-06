# Návrh: Všechny limity a texty nastavitelné v Admin Dashboardu

## Cíl

Jako admin chcete měnit **limity, kvóty a právní texty** v dashboardu, **bez úpravy kódu**. Níže je princip, kde to bude žít a co přesně přidat.

---

## 1. Princip

- **Jedno místo pro „globální“ hodnoty:** tabulka `global_settings` (key/value) – už existuje.
- **Limity tierů:** rozšířit tabulku `license_tiers` o sloupce, které teď jsou jen v kódu (`license_config.py`), a v Adminu je editovat na stránce **Tier definice** (už tam je úprava tierů).
- **Právní / marketingové texty:** ukládat do `global_settings` (nebo jedné tabulky „editable_pages“). V Adminu nová sekce **„Texty a právní“** (nebo „Právní dokumenty“) s formuláři pro úpravu.

Aplikace pak všude **nejdřív čte z DB** (global_settings / license_tiers). Pokud nic není nastavené, použije **výchozí hodnotu z kódu** (fallback), aby po nasazení vše fungovalo i bez vyplnění v Adminu.

---

## 2. Co už v Adminu je

- **Nastavení** (`/admin/settings`): Maintenance Mode, Allow New Registrations, změna hesla admina.
- **Tier definice** (`/admin/tiers`): úprava tieru – Název, Max souborů (dávka), Max zařízení, Podpisy, Čas. razítka, Excel export, Pokročilé filtry.  
  Chybí tam: **denní limit souborů** (daily_files_limit), příp. rate limit za hodinu.

---

## 3. Co doplnit – přehled

### A) Limity a konstanty (nastavitelné v dashboardu)

| Co | Kde je teď | Kam to dát | Kde v Adminu |
|----|------------|------------|----------------|
| **Denní limit souborů (po tieru)** | `license_config.py` → `daily_files_limit` (10 / 500 / 1000) | Sloupec `daily_files_limit` v tabulce `license_tiers` (nebo global_settings per tier) | **Tier definice** – přidat pole „Denní limit souborů“ do formuláře úpravy tieru |
| **Celkový trial limit (na zařízení)** | `database.py` → `TRIAL_LIMIT_TOTAL_FILES = 10` | `global_settings`: klíč např. `trial_limit_total_files` | **Nastavení** – nová sekce „Limity a kvóty“ (nebo rozšířit stávající Nastavení): jedno číslo „Trial – max. souborů na zařízení“ |
| **Rate limit (free check) – za hodinu** | `license_config.py` → `rate_limit_per_hour` (3 / 100 / 1000) | Buď sloupec v `license_tiers`, nebo `global_settings` (např. `rate_limit_free_tier`) | **Nastavení** nebo **Tier definice** |
| **Max. velikost souboru (MB) po tieru** | `license_config.py` → `max_file_size_mb` (10 / 50 / 100) | Sloupec v `license_tiers` nebo global_settings | **Tier definice** (volitelně) |

Doporučení:  
- **Tier definice:** přidat sloupce `daily_files_limit`, `rate_limit_hour`, `max_file_size_mb` do tabulky `license_tiers` a do formuláře na `/admin/tiers`.  
- **Nastavení:** v jedné kartě „Limity a kvóty“ položku **Trial – celkový limit souborů na zařízení** z `global_settings['trial_limit_total_files']`.

V kódu (`api_endpoint.py`, `database.py`, `get_user_license`) pak:  
- u tieru brát limity z `tier_row` z DB (pokud jsou vyplněné), jinak fallback na `license_config.get_tier_limits(tier)`;  
- trial limit brát z `db.get_global_setting('trial_limit_total_files', 10)` (default 10).

---

### B) Texty – disclaimery, VOP, GDPR (editovatelné v dashboardu)

| Text / stránka | Kde je teď | Kam to dát | Kde v Adminu |
|----------------|------------|------------|----------------|
| **VOP (Všeobecné obchodní podmínky)** | Šablona `templates/vop.html` (statický HTML) | `global_settings`: klíč např. `legal_vop_html` (celý HTML obsah) | Nová stránka např. **„Texty a právní“** nebo **„Právní dokumenty“**: editor (textarea nebo jednoduchý WYSIWYG) pro VOP |
| **GDPR (Ochrana osobních údajů)** | Šablona `templates/gdpr.html` (statický HTML) | `global_settings`: klíč `legal_gdpr_html` | Stejná stránka – editor pro GDPR |
| **Disclaimer v patičce / v aplikaci** | Natvrdo v `pdf_check_web_main.py` (HTML string) a v šablonách | `global_settings`: např. `footer_disclaimer`, `app_legal_notice` | Stejná stránka – krátké textové pole „Právní upozornění v patičce“, „Disclaimer v aplikaci“ |
| **Kontaktní e-mail (info@…)** | Různě v šablonách (vop, gdpr, landing) | `global_settings`: `contact_email` | Nastavení nebo „Texty a právní“ – pole „Kontaktní e-mail“ |

Princip zobrazení:  
- Route `/vop` a `/gdpr`: nejdřív načíst z DB (`legal_vop_html` / `legal_gdpr_html`). Pokud je hodnota neprázdná, vykreslit ji (v layoutu šablony); pokud prázdná, zobrazit výchozí obsah z šablony (jako doposud).  
- Před uložením do DB lze z šablony načíst aktuální výchozí text a v Adminu ho nabídnout jako „Výchozí“ / „Obnovit výchozí“.

---

## 4. Struktura v Adminu (návrh menu)

- **Nastavení** (stávající)  
  - Globální přepínače (Maintenance, Allow New Registrations)  
  - **Limity a kvóty:** Trial – max. souborů na zařízení; případně další globální čísla  
  - Změna hesla admina  

- **Tier definice** (stávající + rozšíření)  
  - U každého tieru: Název, Max souborů (dávka), **Denní limit souborů**, Max zařízení, Rate limit/hodinu, Max velikost souboru (MB), zaškrtávátka (Podpisy, Excel, …)  

- **Texty a právní** (nová položka menu)  
  - VOP – editor HTML/textu  
  - GDPR – editor HTML/textu  
  - Krátké texty: disclaimer v patičce, právní upozornění v aplikaci  
  - Kontaktní e-mail  

(Alternativa: „Texty a právní“ sloučit do jedné stránky „Nastavení“ jako další karty; záleží na vás.)

---

## 5. Kroky implementace (shrnutí)

1. **DB**  
   - Přidat do `license_tiers` sloupce: `daily_files_limit`, `rate_limit_hour`, `max_file_size_mb` (s rozumnými defaulty).  
   - V `global_settings` používat klíče: `trial_limit_total_files`, `legal_vop_html`, `legal_gdpr_html`, `footer_disclaimer`, `app_legal_notice`, `contact_email`.

2. **Backend**  
   - Všechna místa, která teď čtou limity z `license_config.py` nebo konstantu `TRIAL_LIMIT_TOTAL_FILES`, upravit tak, aby brala hodnoty z DB (tier_row / global_settings) s fallbackem na stávající výchozí.  
   - Route `/vop` a `/gdpr`: načíst obsah z `global_settings` a při neprázdné hodnotě ho zobrazit; jinak šablonu.  
   - Předávání editovatelných textů (disclaimer, kontakt) do šablon z view (např. z `global_settings`).

3. **Admin UI**  
   - **Nastavení:** sekce „Limity a kvóty“ s polem Trial limit; uložení do `global_settings`.  
   - **Tier definice:** rozšířit formulář a API o nové sloupce; zobrazit je v tabulce a v modalu úpravy.  
   - **Texty a právní:** nová stránka (nebo karta) s formuláři pro VOP, GDPR, disclaimer, kontaktní e-mail; ukládání do `global_settings`.

4. **Migrace**  
   - Skript (nebo jednorázová migrace), který doplní sloupce do `license_tiers` a případně naplní `global_settings` výchozími hodnotami z aktuálních šablon a z `license_config.py`, aby po upgradu vše fungovalo bez ručního vyplňování.

---

## 6. Identita provozovatele (vaše podmínky, IČO, kontakt)

Všechny údaje, které se teď opakují v patičce, VOP, GDPR a e-mailech, by měly jít měnit na jednom místě v Adminu.

| Co | Kde je teď | Kam to dát | Kde v Adminu |
|----|------------|------------|----------------|
| **Jméno / firma provozovatele** | VOP, GDPR, footer (`Ing. Martin Cieślar`) | `global_settings`: `provider_name` | Nová sekce **„Provozovatel“** (v Nastavení nebo „Texty a právní“) |
| **Adresa (sídlo)** | VOP, GDPR (`Porubská 1, 742 83 Klimkovice – Václavovice`) | `global_settings`: `provider_address` (nebo `provider_street`, `provider_city`, `provider_zip`) | Stejná sekce – pole Adresa nebo Ulice, Město, PSČ |
| **IČO** | VOP, GDPR, footer, checkout (`04830661`) | `global_settings`: `provider_ico` | Stejná sekce |
| **Právní doplněk** (např. „FO v ŽR od …“) | VOP, GDPR | `global_settings`: `provider_legal_note` | Stejná sekce – volitelné textové pole |
| **Kontaktní e-mail** | VOP, GDPR, landing, footer (`info@dokucheck.app`) | `global_settings`: `contact_email` (nebo `provider_email`) | Stejná sekce |
| **Bankovní údaje** (pro platby – účet, IBAN, VS) | E-mail po objednávce (volitelně z env) | `global_settings`: `bank_account`, `bank_iban` | Stejná sekce – volitelně |

**Použití:** Šablony VOP, GDPR, patička v aplikaci, checkout a e-mail po objednávce budou brát tyto hodnoty z DB (předané z view). Pokud není nic nastavené, fallback na stávající výchozí text z kódu/šablony.

---

## 7. Cenová politika (tarify, ceny v Kč)

Aby bylo možné měnit ceny a názvy tarifů bez úpravy kódu (checkout, e-mail, landing, portál).

| Co | Kde je teď | Kam to dát | Kde v Adminu |
|----|------------|------------|----------------|
| **Názvy tarifů** (Basic, Pro, Premium) | `TARIF_LABELS` v `pdf_check_web_main.py`, checkout | `global_settings`: např. JSON `pricing_tarifs` nebo klíče `tarif_basic_label`, `tarif_standard_label`, `tarif_premium_label` | Nová stránka nebo karta **„Cenová politika“** |
| **Částky (Kč) za tarif** | `TARIF_AMOUNTS` (`basic: 990, standard: 1990, premium: 4990`), e-mail po objednávce, landing (někde 1 290 / 1 990) | Stejné úložiště – např. `tarif_basic_amount_czk`, `tarif_standard_amount_czk`, `tarif_premium_amount_czk` | Formulář „Cenová politika“: tabulka Tarif | Název | Částka (Kč) |
| **Zobrazení na landingu a v portálu** | Natvrdo v `landing.html`, `portal_dashboard.html` (1 290 Kč, 1 990 Kč) | Číst z týchž nastavení; šablony dostanou `tarif_prices` z view (načtené z DB) | – |

**Doporučení:** Jeden JSON v `global_settings` pod klíčem `pricing_tarifs`, např.  
`{"basic": {"label": "BASIC", "amount_czk": 990}, "standard": {"label": "STANDARD", "amount_czk": 1990}, "premium": {"label": "PREMIUM", "amount_czk": 4990}}`.  
Admin formulář: pro každý tarif (basic, standard, premium) pole „Název“ a „Částka (Kč)“. Checkout, e-mail a landing pak berou ceny a štítky z tohoto JSONu (fallback na současné konstanty, pokud JSON chybí).

---

## 8. Texty na landing page (nadpisy, popisky, CTA, FAQ)

Aby šlo měnit marketingové texty na úvodní / landing stránce bez zásahu do šablon.

| Blok | Příklady textů (teď v kódu/šablonách) | Kam to dát | Kde v Adminu |
|------|----------------------------------------|------------|----------------|
| **Hero** | Nadpis („DokuCheck – Dokumentace bez chyb…“), podnadpis, badge („ONLINE + Desktop“), text u CTA („Kontrola za 2–5 min“), text tlačítek („Vyzkoušet ONLINE Check“, „Stáhnout aplikaci zdarma“) | `global_settings`: `landing_hero_title`, `landing_hero_subtitle`, `landing_hero_badge`, `landing_hero_cta_note`, `landing_cta_primary`, `landing_cta_secondary` | Nová stránka **„Landing / Marketing“** – sekce Hero |
| **Jak to funguje** | Nadpis sekce, kroky 1–3 (název + popis) | `landing_section_how_title`, `landing_step1_title`, `landing_step1_text`, … (nebo jeden JSON `landing_how_steps`) | Stejná stránka – sekce „Jak to funguje“ |
| **Dva režimy** | Nadpis, texty pro „Z Agenta“ a „Cloud“ | `landing_section_modes_title`, `landing_mode_agent_title`, `landing_mode_agent_text`, `landing_mode_cloud_title`, `landing_mode_cloud_text` | Stejná stránka |
| **Ceník** | Nadpis sekce, u každého tarifu: název karty, krátký popis („Pro menší objemy“, „Doporučujeme…“, „Na míru…“) | Lze navázat na „Cenová politika“ + přidat `landing_tarif_basic_desc`, `landing_tarif_standard_desc`, `landing_tarif_premium_desc` | „Cenová politika“ nebo „Landing“ |
| **FAQ** | Otázky a odpovědi (několik párů) | `global_settings`: JSON `landing_faq` = `[{"q": "...", "a": "..."}, ...]` nebo řetězce `landing_faq_1_q`, `landing_faq_1_a`, … | „Landing / Marketing“ – sekce FAQ (seznam položek) |
| **Footer na landingu** | Jedna řádka („Kontakt: … · VOP · GDPR“) | Buď složit z `contact_email` a odkazů, nebo `landing_footer_text` | Volitelně, nebo jen kontakt z Provozovatel |

**Princip:** View pro landing (např. `/`, `/lp-v3`) načte tyto klíče z `global_settings` a předá je do šablony. Šablona používá proměnné (např. `{{ landing_hero_title }}`); pokud je prázdné, zobrazí výchozí text z šablony. V Adminu stačí formulář s poli pro každý blok (Hero, Jak to funguje, Dva režimy, Ceník popisky, FAQ).

---

## 9. Rozšířená struktura menu v Adminu (souhrn)

- **Nastavení**  
  - Globální přepínače (Maintenance, Allow New Registrations)  
  - Limity a kvóty (Trial – max. souborů na zařízení)  
  - **Provozovatel:** jméno, adresa, IČO, právní doplněk, kontaktní e-mail, bankovní údaje (volitelně)  
  - Změna hesla admina  

- **Cenová politika** (nová položka)  
  - Tarify: pro každý (basic, standard, premium) – Název, Částka (Kč); uložení do `pricing_tarifs`  

- **Tier definice**  
  - Stávající + denní limit souborů, rate limit, max velikost souboru  

- **Texty a právní**  
  - VOP, GDPR (editory HTML/textu)  
  - Krátké texty: disclaimer v patičce, právní upozornění v aplikaci  
  - Kontaktní e-mail lze duplicitně i v Provozovatel (jedna hodnota, dvě místa v menu pro přehlednost)  

- **Landing / Marketing** (nová položka)  
  - Hero (nadpis, podnadpis, badge, CTA texty)  
  - Jak to funguje (kroky)  
  - Dva režimy (texty)  
  - Popisky tarifů na landingu (pokud nejsou součástí Cenové politiky)  
  - FAQ (otázky a odpovědi)  

---

## 10. Shrnutí – co budete moci nastavovat bez kódování (rozšířené)

- **Trial a tier:** celkový trial limit, u každého tieru denní limit, max souborů v dávce, max zařízení, rate limit, max velikost souboru, zaškrtávátka (podpisy, Excel, filtry).  
- **Právní:** plný text VOP a GDPR, disclaimer v patičce a v aplikaci.  
- **Identita provozovatele:** jméno/firma, adresa, IČO, právní doplněk (ŽR), kontaktní e-mail, bankovní údaje.  
- **Cenová politika:** názvy tarifů a částky v Kč; zobrazení v checkoutu, e-mailu, landingu a portálu z jednoho místa.  
- **Landing:** hero (nadpis, podnadpis, CTA), „Jak to funguje“, „Dva režimy“, popisky tarifů, FAQ.  

Vše výše by bylo nastavitelné z Admin dashboardu; kód a šablony by sloužily jako výchozí hodnoty a layout.

---

## 11. Kroky implementace (doplněk k bodu 5)

- **DB:** V `global_settings` přidat klíče: `provider_name`, `provider_address`, `provider_ico`, `provider_legal_note`, `contact_email`, `bank_account`, `bank_iban`, `pricing_tarifs` (JSON), `landing_hero_title`, `landing_hero_subtitle`, … (nebo jeden JSON `landing_content`).  
- **Backend:** View pro `/`, `/checkout`, `/vop`, `/gdpr`, e-mail po objednávce a (pokud existuje) portál načtou potřebné klíče z `global_settings` a předají je do šablon; šablony používají proměnné s fallbackem na stávající text.  
- **Admin UI:** Nové stránky nebo karty: Provozovatel, Cenová politika, Landing / Marketing; formuláře ukládají do `global_settings`.

---

## 12. Přehled klíčů v `global_settings` (pro implementaci)

| Klíč | Popis | Výchozí (fallback) |
|------|--------|---------------------|
| **Přepínače** | | |
| `maintenance_mode` | Údržba | false |
| `allow_new_registrations` | Povolit nové registrace | true |
| **Limity** | | |
| `trial_limit_total_files` | Trial – max. souborů na zařízení | 10 |
| **Provozovatel** | | |
| `provider_name` | Jméno / firma | Ing. Martin Cieślar |
| `provider_address` | Sídlo (jedno pole nebo ulice + město + PSČ) | Porubská 1, 742 83 Klimkovice – Václavovice |
| `provider_ico` | IČO | 04830661 |
| `provider_legal_note` | Doplněk (např. FO v ŽR od …) | Fyzická osoba zapsaná v ŽR od … |
| `contact_email` | Kontaktní e-mail | info@dokucheck.app |
| `bank_account` | Číslo účtu (pro platby) | (prázdné nebo z env) |
| `bank_iban` | IBAN | (prázdné) |
| **Cenová politika** | | |
| `pricing_tarifs` | JSON: basic/standard/premium → label, amount_czk | viz TARIF_AMOUNTS, TARIF_LABELS v kódu |
| **Právní texty** | | |
| `legal_vop_html` | Celý obsah stránky VOP (HTML) | šablona vop.html |
| `legal_gdpr_html` | Celý obsah stránky GDPR (HTML) | šablona gdpr.html |
| `footer_disclaimer` | Právní upozornění v patičce | stávající string |
| `app_legal_notice` | Disclaimer v aplikaci | stávající string |
| **Landing** | | |
| `landing_hero_title` | Hero nadpis | DokuCheck – Dokumentace bez chyb… |
| `landing_hero_subtitle` | Hero podnadpis | Rychlá kontrola PDF/PDF-A… |
| `landing_hero_badge` | Badge text | ONLINE + Desktop |
| `landing_cta_primary` | Text primárního CTA | Vyzkoušet ONLINE Check |
| `landing_cta_secondary` | Text sekundárního CTA | Stáhnout aplikaci zdarma |
| `landing_section_how_title` | Nadpis „Jak to funguje“ | Jak to funguje |
| `landing_step1_title`, `landing_step1_text`, … | Kroky (nebo JSON `landing_how_steps`) | z šablony |
| `landing_section_modes_title` | Nadpis „Dva režimy“ | Dva režimy: Z Agenta vs Cloud |
| `landing_mode_agent_title`, `landing_mode_agent_text`, `landing_mode_cloud_*` | Texty režimů | z šablony |
| `landing_tarif_basic_desc`, `landing_tarif_standard_desc`, `landing_tarif_premium_desc` | Krátký popis tarifu na landingu | z šablony |
| `landing_faq` | JSON [{"q":"…","a":"…"}, …] | z šablony |

(Tabulka `license_tiers` má navíc sloupce: `daily_files_limit`, `rate_limit_hour`, `max_file_size_mb`.)

---

Pokud tento princip souhlasí, další krok je konkrétní implementace (migrace DB, úpravy view a šablon, nové/rozšířené stránky v Adminu).
