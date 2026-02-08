# Přehled přístupových adres a rout – www.dokucheck.cz

Dokument vygenerován z `pdf_check_web_main.py`, `admin_routes.py`, `api_endpoint.py`. Soubor `app.py` v projektu není; hlavní aplikace je v `pdf_check_web_main.py`.

---

## Tabulka URL adres a přístupů

| NÁZEV | URL ADRESA | POTŘEBNÉ PŘIHLÁŠENÍ | ÚČEL |
|------|------------|---------------------|------|
| **Hlavní web (landing)** | https://www.dokucheck.cz/ | Ne | Úvodní stránka DokuCheck, texty z `global_settings`. |
| **VOP** | https://www.dokucheck.cz/vop | Ne | Všeobecné obchodní podmínky (`legal_vop_html`). |
| **GDPR** | https://www.dokucheck.cz/gdpr | Ne | Ochrana osobních údajů (`legal_gdpr_html`). |
| **Landing V1 (test)** | https://www.dokucheck.cz/lp/v1 | Ne | Vizuální prototyp landing V1. |
| **Landing V2 (test)** | https://www.dokucheck.cz/lp/v2 | Ne | Vizuální prototyp landing V2. |
| **Landing V3 (test)** | https://www.dokucheck.cz/lp/v3 | Ne | Vizuální prototyp landing V3. |
| **Přihlášení z Agenta (token)** | https://www.dokucheck.cz/auth/from-agent-token?login_token=... | Ne (platný token v URL) | Jednorázový token z Agenta přihlásí uživatele a přesměruje na `/app`. |
| **Hlavní aplikace (kontrola PDF)** | https://www.dokucheck.cz/app | Ne (nebo session po tokenu) | Webová kontrola PDF, výsledky; po přihlášení z Agenta předá `bootstrap_user`. |
| **Stažení aplikace** | https://www.dokucheck.cz/download | Ne | Stránka pro stažení desktop Agenta. |
| **Online kontrola** | https://www.dokucheck.cz/online-check | Ne | Jednorázová online kontrola (demo). |
| **Checkout (objednávka)** | https://www.dokucheck.cz/checkout | Ne | Fakturační formulář; POST ukládá objednávku, e-maily admin + zákazník. |
| **Potvrzení objednávky** | https://www.dokucheck.cz/order-success | Ne | Děkujeme po odeslání objednávky. |
| **Portál (přihlášení)** | https://www.dokucheck.cz/portal | Ne | Přihlášení e-mail + heslo (účet z `api_keys`). |
| **Portál – odhlášení** | https://www.dokucheck.cz/portal/logout | Ano (session) | Odhlášení z portálu. |
| **Portál – změna hesla** | https://www.dokucheck.cz/portal/change-password | Ano (POST) | Změna hesla uživatele (api_keys.password_hash). |
| **Analyze (POST)** | https://www.dokucheck.cz/analyze | Ne | Analýza (POST). |
| **Výběr složky** | https://www.dokucheck.cz/select_folder | Ne | UI pro výběr složky. |
| **API – scan stream** | https://www.dokucheck.cz/api/scan-folder-stream | Ne | Stream skenování složky. |
| **API – scan folder** | https://www.dokucheck.cz/api/scan-folder | Ne (POST) | Skenování složky (POST). |
| **Admin – přihlášení** | https://www.dokucheck.cz/login | Ne | Přihlášení do Admin dashboardu. Heslo: tabulka `admin_users` (password_hash). |
| **Admin – odhlášení** | https://www.dokucheck.cz/logout | Ano (admin session) | Odhlášení admina. |
| **Admin – dashboard** | https://www.dokucheck.cz/admin | Ano (admin) | Hlavní přehled Admin dashboardu. |
| **Admin – dashboard (alias)** | https://www.dokucheck.cz/admin/dashboard | Ano (admin) | Stejné jako `/admin`. |
| **Admin – uložení e-mailových šablon** | https://www.dokucheck.cz/admin/save-email-templates | Ano (POST) | Uložení šablon (order_confirmation, activation, footer). |
| **Admin – test e-mailu** | https://www.dokucheck.cz/admin/send-test-email | Ano (POST) | Odeslání testovacího e-mailu. |
| **Admin – uživatelé** | https://www.dokucheck.cz/admin/users | Ano | Seznam uživatelů (licence). |
| **Admin – audit uživatelů** | https://www.dokucheck.cz/admin/users/audit | Ano | Audit uživatelů. |
| **Admin – tarify** | https://www.dokucheck.cz/admin/tiers | Ano | Správa tarifů (license_tiers). |
| **Admin – čekající objednávky** | https://www.dokucheck.cz/admin/pending-orders | Ano | Nové objednávky, čekající na platbu, aktivní licence. |
| **Admin – vygenerovat fakturu a poslat** | https://www.dokucheck.cz/admin/generate-invoice-and-send | Ano (POST) | Vygeneruje PDF, pošle zákazníkovi, status → WAITING_PAYMENT. |
| **Admin – přepínač ČSOB** | https://www.dokucheck.cz/admin/toggle-auto-activate-csob | Ano (POST) | Automatická aktivace po platbě (ČSOB). |
| **Admin – potvrdit platbu** | https://www.dokucheck.cz/admin/confirm-payment | Ano (POST) | Status → ACTIVE, vytvoření licence, aktivační e-mail. |
| **Admin – trial** | https://www.dokucheck.cz/admin/trial | Ano | Správa trial. |
| **Admin – logy** | https://www.dokucheck.cz/admin/logs | Ano | Systémové logy. |
| **Admin – nastavení** | https://www.dokucheck.cz/admin/settings | Ano (GET/POST) | Globální nastavení (SMTP, provider, banka, texty). |
| **Admin – reset trial** | https://www.dokucheck.cz/admin/api/trial/reset | Ano (POST) | API: reset trial. |
| **Admin – aktualizace tieru** | https://www.dokucheck.cz/admin/api/tier/update | Ano (POST) | API: update tier. |
| **Admin – aktivita** | https://www.dokucheck.cz/admin/api/activity | Ano | API: aktivita. |
| **Admin – KPIs** | https://www.dokucheck.cz/admin/api/stats/kpis | Ano | API: KPI statistiky. |
| **Admin – žebříček uživatelů** | https://www.dokucheck.cz/admin/api/stats/users-ranking | Ano | API: žebříček. |
| **Admin – statistiky trial** | https://www.dokucheck.cz/admin/api/stats/trial | Ano | API: trial statistiky. |
| **Admin – uživatelé podle tieru** | https://www.dokucheck.cz/admin/api/users-by-tier | Ano | API: uživatelé podle tieru. |
| **Admin – vytvoření licence** | https://www.dokucheck.cz/admin/api/license/create | Ano (POST) | API: vytvoření licence. |
| **Admin – aktualizace licence** | https://www.dokucheck.cz/admin/api/license/update | Ano (POST) | API: aktualizace licence (tier, heslo, atd.). |
| **Admin – uvítací balíček** | https://www.dokucheck.cz/admin/api/license/welcome-package | Ano (POST) | API: vygenerování hesla a textu uvítacího e-mailu. |
| **Admin – nastavení hesla licence** | https://www.dokucheck.cz/admin/api/license/set-password | Ano (POST) | API: nastavení hesla uživatele (api_keys). |
| **Admin – billing licence** | https://www.dokucheck.cz/admin/api/license/billing | Ano (GET/POST) | API: billing údaje licence. |
| **Admin – zap/vyp licence** | https://www.dokucheck.cz/admin/api/license/toggle | Ano (POST) | API: zapnutí/vypnutí licence. |
| **Admin – reset zařízení** | https://www.dokucheck.cz/admin/api/license/reset-devices | Ano (POST) | API: reset device binding. |
| **Admin – smazání licence** | https://www.dokucheck.cz/admin/api/license/delete | Ano (POST) | API: smazání licence. |
| **Admin – změna hesla admina** | https://www.dokucheck.cz/admin/change-password | Ano (GET/POST) | Změna hesla přihlášeného admina (admin_users). |
| **Admin – git pull** | https://www.dokucheck.cz/admin/api/git-pull | Ano (POST) | API: git pull na serveru. |
| **Admin – zařízení licence** | https://www.dokucheck.cz/admin/api/license/<api_key>/devices | Ano | API: seznam zařízení pro danou licenci. |
| **Admin – setup** | https://www.dokucheck.cz/setup | Ne (nebo omezeně) | Prvotní nastavení admin účtu. |
| **API – batch create** | https://www.dokucheck.cz/api/batch/create | Ano (API key / session) | Vytvoření dávky. |
| **API – batch upload** | https://www.dokucheck.cz/api/batch/upload | Ano | Nahrání souborů do dávky. |
| **API – batch finalize** | https://www.dokucheck.cz/api/batch/<batch_id>/finalize | Ano | Finalizace dávky. |
| **API – batch delete** | https://www.dokucheck.cz/api/batch/<batch_id> | Ano (DELETE) | Smazání dávky. |
| **API – all-data delete** | https://www.dokucheck.cz/api/all-data | Ano (DELETE) | Smazání všech dat. |
| **API – results** | https://www.dokucheck.cz/api/results | Ano (POST) | Odeslání výsledků. |
| **API – auth verify** | https://www.dokucheck.cz/api/auth/verify | Ano (API key) | Ověření API klíče. |
| **API – user login** | https://www.dokucheck.cz/api/auth/user-login | Ne (POST, e-mail + heslo) | Přihlášení e-mail + heslo (api_keys). |
| **API – one-time login token** | https://www.dokucheck.cz/api/auth/one-time-login-token | Ano (POST) | Vygenerování jednorázového tokenu pro web. |
| **API – session from token** | https://www.dokucheck.cz/api/auth/session-from-token | Ne (token v parametru) | Session z jednorázového tokenu. |
| **API – generate key** | https://www.dokucheck.cz/api/generate-key | Ano (POST) | Generování API klíče. |
| **API – stats** | https://www.dokucheck.cz/api/stats | Ano | Statistiky. |
| **API – results list** | https://www.dokucheck.cz/api/results/list | Ano | Seznam výsledků. |
| **API – agent results** | https://www.dokucheck.cz/api/agent/results | Ano | Výsledky pro agenta. |
| **API – agent batch export** | https://www.dokucheck.cz/api/agent/batch/<batch_id>/export | Ano | Export dávky (např. xlsx). |
| **API – agent export all** | https://www.dokucheck.cz/api/agent/export-all | Ano | Export všech dat. |
| **API – validate license** | https://www.dokucheck.cz/api/auth/validate-license | Ano (POST) | Ověření licence. |
| **API – register device** | https://www.dokucheck.cz/api/auth/register-device | Ano (POST) | Registrace zařízení. |
| **API – devices** | https://www.dokucheck.cz/api/auth/devices | Ano | Seznam zařízení. |
| **API – device delete** | https://www.dokucheck.cz/api/auth/device/<hwid> | Ano (DELETE) | Smazání zařízení. |
| **API – license info** | https://www.dokucheck.cz/api/license/info | Ano | Informace o licenci. |
| **API – agent config** | https://www.dokucheck.cz/api/agent-config | Ano | Konfigurace pro agenta. |
| **API – free-check status** | https://www.dokucheck.cz/api/free-check/status | Ne | Status free check. |
| **API – free-check record** | https://www.dokucheck.cz/api/free-check/record | Ne (POST) | Záznam free check. |
| **API – admin create license** | https://www.dokucheck.cz/api/admin/create-license | Ano (POST) | Admin API: vytvoření licence. |
| **API – admin upgrade license** | https://www.dokucheck.cz/api/admin/upgrade-license | Ano (POST) | Admin API: upgrade licence. |
| **API – admin list licenses** | https://www.dokucheck.cz/api/admin/list-licenses | Ano | Admin API: seznam licencí. |
| **API – deploy** | https://www.dokucheck.cz/api/deploy | Ne | Informace o deployi. |

---

## Hesla načítaná ze systému (Environment Variables / WSGI)

- **MAIL_PASSWORD** – heslo k SMTP (info@dokucheck.cz). Načítá se v `pdf_check_web_main.py` jako `os.environ.get('MAIL_PASSWORD', '')` a předává se do Flask-Mail / `email_sender`. Na PythonAnywhere lze nastavit v **Web → Vaše aplikace → Environment variables** nebo v WSGI před importem aplikace (`os.environ['MAIL_PASSWORD'] = '...'`).
- **SECRET_KEY** – klíč pro Flask session. Načítá se v `pdf_check_web_main.py` jako `os.environ.get('SECRET_KEY', '...')`. Pokud není nastaven, používá se výchozí řetězec (viz upozornění níže).
- **ADMIN_SECRET_KEY** – v `admin_routes.py` jako `os.environ.get('ADMIN_SECRET_KEY', '...')`. Slouží pro admin session/bezpečnost. Není-li nastaven, používá se výchozí hodnota (viz níže).

---

## Kde jsou v databázi uložena hesla

- **Admin přihlášení:** tabulka **`admin_users`**, sloupec **`password_hash`**. Hash je PBKDF2-HMAC-SHA256 s národní solí (viz `database.py`: `_hash_password`, `_verify_password`, `verify_admin_login`, `create_admin_user`, `update_admin_user`).
- **Uživatelé portálu / Agenta (e-mail + heslo):** tabulka **`api_keys`**, sloupec **`password_hash`**. Stejný formát hashe. Používá se pro přihlášení na `/portal` a pro API `/api/auth/user-login` (viz `database.py`: `verify_license_password`, `admin_set_license_password`, `create_api_key_with_license`, atd.).

---

## Upozornění: hesla nebo citlivé řetězce „natvrdo“ v kódu

Níže jsou místa, kde je v kódu uveden výchozí nebo testovací řetězec. V produkci by měly být nahrazeny proměnnými prostředí nebo bezpečným nastavením.

1. **`pdf_check_web_main.py`**  
   - **SECRET_KEY:**  
     `app.secret_key = os.environ.get('SECRET_KEY', 'pdfcheck_secret_key_2025_change_in_production')`  
     Pokud není nastaveno `SECRET_KEY` v prostředí, používá se tento řetězec. **Doporučení:** v produkci nastavit `SECRET_KEY` v Environment variables a tento fallback odstranit nebo nepoužívat.

2. **`admin_routes.py`**  
   - **Výchozí admin přihlášení:**  
     `DEFAULT_ADMIN_EMAIL = 'admin@admin.cz'`  
     `DEFAULT_ADMIN_PASSWORD = 'admin'`  
     Tyto konstanty se používají v `ensure_default_admin()` a `reset_default_admin_password()` – účet admin@admin.cz má tedy výchozí heslo **`admin`**. To je v kódu natvrdo. **Doporučení:** po prvním přihlášení heslo změnit (Admin → Změna hesla) a v produkci zvážit odstranění nebo vypnutí `ensure_default_admin()` / použití jiného mechanismu prvního nastavení.
   - **ADMIN_SECRET_KEY:**  
     `ADMIN_SECRET_KEY = os.environ.get('ADMIN_SECRET_KEY', 'pdfcheck_admin_secret_2025')`  
     Fallback je natvrdo. **Doporučení:** v produkci nastavit `ADMIN_SECRET_KEY` v Environment variables.

3. **`admin_routes.py` – funkce vracející testovací data**  
   - V objektu vráceném z funkce (např. pro init test data) je **`'admin_password': 'admin123'`** a **`'admin_email': 'admin@pdfcheck.cz'`**. Toto je testovací výstup (např. pro tisk do konzole), ne přihlašovací účet přímo v DB, ale heslo je v kódu plaintext. **Doporučení:** v produkci tuto funkci nespouštět nebo vrácený slovník neobsahovat reálná hesla; případně je brát z env.

4. **`init_test_data.py`**  
   - Komentář a logika uvádějí testovací účet **admin@pdfcheck.cz** s heslem **admin** nebo **admin123**. Pokud se tento skript používá jen lokálně pro testy, je vhodné zajistit, aby se nikdy nespouštěl v produkci a aby se hesla nelogovala.

**Shrnutí:**  
- V produkci by neměla zůstat výchozí hesla **admin** / **admin123** ani v kódu ani jako skutečné heslo účtu.  
- Všechna „secret“ a SMTP hesla by měla jít z Environment variables (WSGI nebo Web → Environment variables na PythonAnywhere), ne z fallbacků v kódu.
