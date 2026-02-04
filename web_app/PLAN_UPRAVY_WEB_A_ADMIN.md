# Plán úprav: Web, Admin, Logy, Nastavení

## 1. Zamčené funkce (Basic) – jednotná hláška a viditelný zámeček

**Kde:** `web_app/pdf_check_web_main.py` (frontend)

- **Hláška:** U všech zamčených prvků (Excel, CSV, Export vše, Filtry) se při kliknutí zobrazí stejná alert: *"Tato funkce vyžaduje Pro licenci nebo vyšší. Upgradujte pro odemčení všech funkcí."* (funkce `checkFeatureAccess` už to dělá – zajistit, že se volá i u filtrů a u kliknutí na zámeček.)
- **Zámeček viditelnější:** CSS `.feature-locked` – zvětšit ikonu 🔒 (např. `font-size: 1.5em`), případně přidat overlay s textem „Pro“.
- **Filtry u názvů sloupců:** V tabulce výsledků jsou dropdown filtry v hlavičce sloupců (PDF/A, Podpis, Podpisovatel, ČKAIT, Razítko). Při Basic je zablokovat: na klik na hlavičku s filtrem volat `checkFeatureAccess('advanced_filters')` a při neúspěchu zobrazit hlášku a neotevřít dropdown.

---

## 2. Globální definice tierů – omezení filtrů

**Kde:** `web_app/database.py`, `web_app/migrate_tiers.py`, `web_app/templates/admin_tiers.html`, `web_app/admin_routes.py`, API sestavení features

- V tabulce `license_tiers` **přidat sloupec** `allow_advanced_filters` (BOOLEAN, default 0).
- Migrace: Trial, Pro, Unlimited = 1; Basic = 0.
- V Admin → Tier definice přidat řádek „Pokročilé filtry“ (checkbox) a ukládat do `allow_advanced_filters`.
- V API při sestavování `features` z tieru používat `allow_advanced_filters`: pokud 1, přidat `advanced_filters`, `tsa_filter`, atd.; pokud 0, nepřidat (Basic bez filtrů).

---

## 3. Admin dashboard – Upravit uživatele, heslo viditelné

**Kde:** `web_app/templates/admin_dashboard.html`, `web_app/admin_routes.py`

- **Tlačítko „Upravit uživatele“:** Vedle „PRODLOUŽIT“ přidat tlačítko „Upravit“ (nebo přejmenovat PRODLOUŽIT na „Upravit / Prodloužit“), které otevře stávající edit modal s **všemi** poli: jméno, e-mail, tier, expirace, heslo (nové). Jedno místo pro kompletní úpravu uživatele.
- **Heslo v modalu pro admina viditelné:** V modalu „Heslo“ (změna hesla) a v edit modalu použít pro pole nového hesla `type="text"` místo `type="password"`, aby admin viděl, co píše (pouze při zadávání nového hesla; stávající heslo nelze zobrazit, je uloženo jako hash).

---

## 4. Portál uživatele – sekce Nastavení (po přihlášení na webu)

**Kde:** `web_app/pdf_check_web_main.py` (šablona/sekce v layoutu), případně `web_app/templates/` (portal)

- Po přihlášení na webu přidat v sidebaru nebo v hlavičce **sekci „Nastavení“** s:
  - **Výměna hesla:** formulář (současné heslo, nové heslo, potvrzení) – volání stávajícího endpointu pro změnu hesla.
  - **Upgrade licence:** tlačítko „Upgrade licence“, po kliknutí zobrazení tarifů Basic a Pro (text + ceny) a tlačítko **„Požádat o upgrade“**.
- **Chování „Požádat o upgrade“:**  
  - **Varianta A (doporučeno):** Otevřít `mailto:VAS_EMAIL?subject=Žádost o upgrade&body=Předvyplněný text (jméno, email, současný tarif)`. Admin si e-mail nadefinuje v konfiguraci (např. `UPGRADE_REQUEST_EMAIL`).
  - **Varianta B:** Formulář na webu, který uloží žádost do DB a backend pošle e-mail (vyžaduje SMTP konfiguraci).

---

## 5. Logy – vázat na jméno uživatele

**Kde:** `web_app/database.py`, `web_app/admin_routes.py`, `web_app/templates/admin_logs.html`

- V tabulce `user_logs` je `user_id` = api_key. V Admin → Logy se nyní zobrazuje zkrácený api_key („user s divným číslem“).
- **Úprava:** Při načítání logů dělat JOIN s `api_keys` (na `user_logs.user_id = api_keys.api_key`) a do šablony předat pro každý záznam **zobrazené jméno**: `user_name` nebo `email` (nebo fallback api_key). V šabloně v sloupci „User“ zobrazit toto jméno místo api_key.
- Implementace: rozšířit `get_user_logs` / `get_logs_filtered` o vrácení `user_display_name` (např. z JOIN s api_keys), nebo v route po načtení logů pro každý řádek dohledat jméno z api_keys a předat do šablony.

---

## 6. Stanice a IP v přehledu uživatelů (dashboard)

**Kde:** `web_app/database.py` (get_all_licenses_with_details nebo ekvivalent), `web_app/templates/admin_dashboard.html`

- V přehledu uživatelů (Admin dashboard) přidat informaci **z jakých stanic a IP se uživatel přihlašoval**.
- **Data:**  
  - Počet stanic = počet záznamů v `user_devices` pro daného uživatele (nebo již vrácené `active_devices`).  
  - Poslední / přehled IP = z `user_logs` (např. poslední 1–3 unikátní IP nebo poslední IP).
- **Implementace:** Rozšířit dotaz (nebo dodatečný dotaz) v metodě, která vrací seznam licencí pro dashboard, o:  
  - `last_ip` = poslední ip_address z user_logs pro daný api_key,  
  - případně `devices_summary` = počet zařízení (už máme active_devices) a seznam machine_name.  
- V šabloně přidat sloupec „Stanice / IP“ nebo dva sloupce: „Stanice“ (počet + tooltip se jmény) a „Poslední IP“.

---

## Pořadí implementace

1. **Logy – jméno uživatele** (DB/route + šablona)  
2. **Zamčené funkce – zámeček a filtry v hlavičkách** (frontend)  
3. **Tier definice – allow_advanced_filters** (migrace, DB, admin tiers, API)  
4. **Admin – Upravit uživatele, heslo viditelné** (šablona dashboard)  
5. **Přehled uživatelů – stanice a IP** (DB + šablona)  
6. **Portál – sekce Nastavení (heslo + upgrade)** (šablona + mailto nebo konfigurace)

---

## Co kde dělat – souhrn

| Úkol | Soubor(y) | Akce |
|------|-----------|------|
| Hláška + zámeček + filtry v hlavičkách | pdf_check_web_main.py | checkFeatureAccess u filtrů sloupců, CSS .feature-locked, blokovat dropdown u Basic |
| Tier – filtry | database.py, migrate_tiers.py, admin_tiers.html, api_endpoint.py | Sloupec allow_advanced_filters, migrace, UI v Admin, features z tieru |
| Admin – Upravit, heslo | admin_dashboard.html | Tlačítko Upravit, v modalu Heslo input type="text" |
| Nastavení uživatele | pdf_check_web_main.py (layout), šablona | Sekce Nastavení, výměna hesla, Upgrade + mailto |
| Logy – jméno | database.py, admin_routes.py, admin_logs.html | JOIN api_keys, zobrazit user_name/email |
| Stanice/IP v přehledu | database.py, admin_dashboard.html | last_ip, devices v license data, nový sloupec v tabulce |
