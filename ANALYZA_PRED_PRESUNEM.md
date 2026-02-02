# Analýza před přesunem (Úkol 2)

Dokument popisuje hlavní soubory Agenta a Webové aplikace a jejich propojení. **Soubory zatím nebyly přesunuty.**

---

## 1. Hlavní soubory Agenta pro PDF Check a jejich funkcionalita

Agent se nachází v `PDF_DOKU_Final/pdfcheck_agent/`. Pro **kontrolu PDF** (bez modulu podepisování) jsou klíčové tyto soubory:

| Soubor | Funkcionalita |
|--------|----------------|
| **agent.py** | Hlavní entry point. Třída `PDFCheckAgent`: načte `config.yaml`, vytvoří `LicenseManager`, spustí GUI (`create_app` z ui.py). Zajišťuje: kontrolu PDF (jeden soubor / více souborů / složka), odeslání výsledků na API (batch), ověření API klíče, přihlášení e-mailem+heslem, odhlášení, zobrazení stavu licence, limit souborů dle tieru. Volá `pdf_checker.analyze_*` a `license_manager.upload_batch` / `verify_api_key` / `get_license_info`. |
| **ui.py** | GUI (tkinter). Třída `PDFCheckUI`: fronta úkolů (složky/soubory), drag & drop, tlačítka Přidat/Vymazat, spuštění kontroly, progress, zobrazení výsledků. Dialog pro aktivaci licence (API klíč nebo e-mail+heslo). Zobrazení „Přihlášen: email (tier)“, odhlášení, odkaz „Otevřít web“. Callbacky předané z agent.py: `on_check_callback`, `on_api_key_callback`, `on_login_password_callback`, `on_logout_callback`, `on_get_max_files`, `on_get_web_login_url`. |
| **pdf_checker.py** | Logika kontroly PDF. Funkce: `check_pdfa_version(content)`, `extract_all_signatures(content)` (ČKAIT/ČKA, TSA, jméno z CN), `analyze_pdf_file(filepath)` (vrací výsledek s `results.pdf_format`, `results.signatures`), `analyze_multiple_pdfs(paths, progress_callback)`, `analyze_folder(folder, progress_callback)`. Žádné volání sítě – pouze analýza binárního obsahu PDF. |
| **license.py** | Třída `LicenseManager`: načte/uloží `config.yaml` (api.url, api.key, agent.auto_send, agent.show_results_window). Metody: `verify_api_key(api_key)` → GET `{api_url}/api/auth/verify` (Bearer), `save_api_key`, `login_with_password(email, password)` → POST `{api_url}/api/auth/user-login`, `get_license_info(api_key)` → GET `{api_url}/api/license/info`, `upload_batch(batch_name, source_folder, results)` → POST `{api_url}/api/batch/upload` (Bearer, JSON). |
| **config.yaml** | Konfigurace agenta: `api.url` (např. https://cieslar.pythonanywhere.com), `api.key` (prázdný nebo uložený API klíč), `agent.auto_send`, `agent.show_results_window`. |

**Pozn.:** V `pdfcheck_agent` jsou i soubory modulu podepisování (pdf_converter, pdf_converter_gui.py, config.json, …). Ty nepatří do „Agenta pro kontrolu PDF“ a mají jít do `archived_signing_module`.

---

## 2. Soubory Webové aplikace a propojení s Agentem (API endpointy)

Web je v `PDF_DOKU_Final/v42/`.

### Hlavní soubory

| Soubor | Funkcionalita |
|--------|----------------|
| **pdf_dokucheck_pro_v41_with_api.py** | Hlavní Flask aplikace. Registruje `register_api_routes(app)` a blueprint `admin_bp`. Šablona HTML (render_template_string), uvolnění portu, spuštění serveru. Režimy: „Z Agenta“ (data z API) a „Lokální“ (upload/disk). |
| **api_endpoint.py** | Všechny API route. `register_api_routes(app)` registruje endpointy níže. Používá `Database`, `license_config`, `feature_manager`. |
| **database.py** | SQLite: tabulky `api_keys`, `batches`, `check_results`, `device_activations`, `rate_limits`. Metody: `verify_api_key`, `create_batch`, `save_result`, `get_agent_results_grouped`, `get_user_license`, `verify_license_password`, `get_license_by_email`, atd. |
| **license_config.py** | Definice tierů (Free/Basic/Pro/Enterprise), feature flags, limity (`get_tier_limits`, `get_tier_features`), JWT-like tokeny pro licenci. |
| **feature_manager.py** | Feature flags podle api_key / tieru (např. `create_manager_from_api_key`). |
| **admin_routes.py** | Blueprint: `/login`, `/logout`, `/admin` – správa licencí (vytváření, úprava, hesla uživatelů). |
| **templates/** | admin_login.html, admin_dashboard.html, admin_change_password.html, admin_setup.html. |

### API endpointy, které Agent používá

| Endpoint | Metoda | Použití v Agentu |
|----------|--------|-------------------|
| **/api/auth/verify** | GET | `LicenseManager.verify_api_key()` – ověření platnosti API klíče (hlavička `Authorization: Bearer {api_key}`). |
| **/api/auth/user-login** | POST | `LicenseManager.login_with_password(email, password)` – přihlášení e-mailem a heslem; vrací `api_key`, `user_name`, `email`, `tier_name`. Agent uloží `api_key` do config.yaml. |
| **/api/license/info** | GET | `LicenseManager.get_license_info(api_key)` – informace o licenci (tier, limits, email, user_name). Agent z toho bere např. limit souborů a zobrazení v UI. |
| **/api/batch/upload** | POST | `LicenseManager.upload_batch(batch_name, source_folder, results)` – odeslání celého batch výsledků kontroly (JSON). Server ověří API klíč a ukládá do `batches` + `check_results`. Limit počtu souborů dle tieru (Free = 5). |
| **/api/auth/one-time-login-token** | POST | Agent volá s Bearer api_key; server vrátí `login_url` s jednorázovým tokenem. Slouží k tlačítku „Otevřít web“ – v prohlížeči se uživatel automaticky přihlásí. |

### Další endpointy (web nebo admin)

- **GET /api/agent/results** – web načítá batche a výsledky pro přihlášeného uživatele (Bearer api_key).
- **GET /api/agent/batch/<batch_id>/export**, **GET /api/agent/export-all** – export do Excelu (openpyxl).
- **DELETE /api/batch/<batch_id>**, **DELETE /api/all-data** – mazání dat uživatele.
- Admin: vytváření/úprava licencí, změna hesel, git-pull na serveru.

---

## 3. Jak Agent ověřuje licenci proti Webové aplikaci

- **Konfigurace URL:** Agent má v `config.yaml` položku `api.url` (např. `https://cieslar.pythonanywhere.com`). Všechny requesty jdou na `{api.url}/api/...`.

- **Dva způsoby „přihlášení“:**  
  1. **API klíč** – uživatel vloží klíč v dialogu; agent zavolá `GET /api/auth/verify` (Bearer klíč). Pokud server vrátí 200, klíč je platný a agent ho uloží do config.yaml.  
  2. **E-mail + heslo** – agent zavolá `POST /api/auth/user-login` s `{ "email", "password" }`. Server v `database.verify_license_password()` ověří heslo proti `api_keys.password_hash`; při úspěchu vrátí `api_key`. Agent tento klíč uloží a dále ho používá jako Bearer.

- **Autorita je na serveru:** Platnost klíče i licence (tier, expirace) jsou v SQLite na webu (`api_keys`, licence_tier, license_expires, password_hash). Agent pouze posílá klíč a server rozhodne (verify_api_key, get_user_license). Při upload batch server kontroluje limit podle tieru (Free = max 5 souborů v jednom batchi).

- **Zobrazení stavu v Agentu:** Po přihlášení agent volá `GET /api/license/info` (Bearer api_key) a z odpovědi bere např. `tier_name`, `limits.max_files_per_batch` a zobrazí je v UI („Přihlášen: email (tier)“). Při prvním spuštění nebo při neplatném klíči agent zobrazí dialog pro aktivaci licence (klíč nebo e-mail+heslo).

Shrnutí: Agent **neověřuje licenci sám** – vždy posílá API klíč (nebo e-mail+heslo) na web a web vrací úspěch/neúspěch a údaje o licenci. Veškerá autorita je na straně webové aplikace a databáze.

---

## 4. Připravenost na přenositelnost (Úkol 3) – požadavky

- **desktop_agent:** V `pdfcheck_agent` již existuje `requirements.txt` (requests, PyYAML, pikepdf, tkinterdnd2, pyhanko, …). Pro **pouze PDF Check** (bez podepisování) stačí: `requests`, `PyYAML`, `tkinterdnd2`. (pikepdf není potřeba pro samotnou kontrolu – pdf_checker pracuje s raw byty; pokud by byl použit jinde, nechat pikepdf.)
- **web_app:** Ve v42 **není** soubor `requirements.txt`. Z kódu vyplývá: `Flask`, `openpyxl` (export Excel). Standardní knihovny: sqlite3, json, secrets, time, hmac, base64 – bez externích balíčků pro JWT (vlastní implementace v license_config).
- **archived_signing_module:** Bude mít vlastní `requirements.txt` (pyhanko, pikepdf, cryptography, tkinterdnd2, …) podle stávajícího pdfcheck_agent/requirements.txt pro podepisování.

Doporučení: V každé složce (`web_app`, `desktop_agent`, `archived_signing_module`) mít soubor `requirements.txt`, aby po přesunu šlo na novém PC spustit `pip install -r requirements.txt` v příslušné složce a aplikace běžela.

---

## 5. Návrh přejmenování hlavních spouštěcích souborů (Úkol 4)

| Aktuální | Navrhovaný | Důvod |
|----------|------------|--------|
| **agent.py** (v desktop_agent) | **pdf_check_agent_main.py** | Název jasně říká, že jde o hlavní vstup bodu agenta pro kontrolu PDF. |
| **pdf_dokucheck_pro_v41_with_api.py** (v web_app) | **web_app_main.py** nebo **pdf_check_web.py** | Jednoznačné označení hlavního souboru webové aplikace; verze v41 může zůstat v komentáři nebo v dokumentaci. |

Soubor `agent.py` je v kódu uváděn jako „PDF DokuCheck Desktop Agent“; přejmenování na `pdf_check_agent_main.py` nevyžaduje změny v importech (ostatní moduly ho neimportují, spouští se přímo). U webu bude potřeba upravit WSGI nebo skripty, které spouštějí aplikaci (odkaz na nový název souboru).

---

*Dokument vytvořen v rámci přípravy reorganizace do PDF_CHECK_SW. Po schválení analýzy lze provést přesun a doplnění requirements.txt.*
