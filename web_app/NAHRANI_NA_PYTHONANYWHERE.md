# Automatické nahrávání na PythonAnywhere

Aby se s nasazením nemuselo otravovat ručně, máte dvě cesty: **Git** (doporučené) a **deploy skript** s PythonAnywhere API pro reload.

---

## 1. Git workflow (doporučené)

**Myšlenka:** Verze archivujete v gitu (commit + tag), na PythonAnywhere máte stejný repozitář naklonovaný. Po otestování uděláte push a na serveru jen `git pull` + reload.

### Na vašem PC (jednou)

1. Ve složce s projektem (např. `c:\Claude` nebo tam, kde je složka `41`) inicializujte git, pokud ještě není:
   ```bash
   git init
   git remote add origin https://github.com/VAS_USER/VAS_REPO.git
   ```
2. Do `.gitignore` přidejte např.:
   ```
   __pycache__/
   *.pyc
   *.db
   deploy_config.env
   .env
   ```
3. První commit a push:
   ```bash
   git add 41/
   git commit -m "v41 - web + API + admin"
   git push -u origin main
   ```

### Na PythonAnywhere (jednou)

1. Přihlaste se na [pythonanywhere.com](https://www.pythonanywhere.com/), záložka **Consoles** → **Bash**.
2. Naklonujte repozitář (nahraďte URL a cestu):
   ```bash
   cd ~
   git clone https://github.com/VAS_USER/VAS_REPO.git cieslar.pythonanywhere.com
   cd cieslar.pythonanywhere.com
   ```
3. Nastavte WSGI tak, aby ukazoval na správný soubor (např. `41/cieslar_pythonanywhere_com_wsgi.py` nebo cestu, kterou máte v záložce Web).
4. V záložce **Web** nastavte **Source code** a **WSGI** na tuto složku/soubor a uložte.

### Při každém nasazení nové verze

**Na PC:**

- Otestujte lokálně.
- Commit + push:
  ```bash
  cd c:\Claude
  git add 41/
  git commit -m "Deploy v41 - popis změn"
  git push
  ```
- Volitelně tag (archivace verze):
  ```bash
  git tag v41-2026-01-31
  git push --tags
  ```

**Na PythonAnywhere:**

- V **Bash** konzoli:
  ```bash
  cd ~/cieslar.pythonanywhere.com
  git pull
  ```
- V záložce **Web** klikněte na **Reload** (zelené tlačítko).

Tím nahrajete jen to, co je v gitu – ručně nic nekopírujete.

---

## 2. Deploy skript (Git + automatický reload)

Ve složce **41** je skript `deploy_to_pythonanywhere.py`, který:

1. Z commitnutých změn udělá **commit** a **push** (pokud jste v gitu).
2. Volitelně přes **SSH** na PythonAnywhere spustí **git pull** (potřebujete platný účet s SSH).
3. Zavolá **PythonAnywhere API** a udělá **Reload** webové aplikace (nemusíte klikat na Reload v prohlížeči).

### Nastavení (jednou)

1. Získejte **API token**: [Account → API Token](https://www.pythonanywhere.com/account/#api_token).
2. Ve složce `41` zkopírujte konfiguraci a vyplňte ji:
   ```bash
   copy deploy_config.example.env deploy_config.env
   ```
   V `deploy_config.env` nastavte:
   - `PA_USERNAME` = vaše PythonAnywhere přihlašovací jméno  
   - `PA_API_TOKEN` = token z účtu  
   - `PA_DOMAIN` = např. `cieslar.pythonanywhere.com`

3. Soubor `deploy_config.env` **necommitujte** do gitu (je v `.gitignore` nebo ho tam nepřidávejte).

### Spuštění deploye

Z příkazové řádky (z složky kde je `41`, nebo z `41`):

```bash
cd c:\Claude\41
python deploy_to_pythonanywhere.py
```

Skript:

- udělá `git add`, `git commit` (když jsou změny) a `git push`;
- pokud máte v `deploy_config.env` vyplněné `PA_SSH` a `PA_APP_PATH`, přes SSH na PA spustí `git pull`;
- pokud máte vyplněné `PA_USERNAME`, `PA_API_TOKEN`, `PA_DOMAIN`, zavolá API a udělá **Reload** web appu.

Bez SSH budete po každém push na PythonAnywhere v Bash ručně spouštět `git pull`; Reload se dá dělat automaticky přes API (stačí vyplnit token a doménu).

---

## 3. Co na web dávat (připomínka)

Na server patří obsah složky **41** (WSGI, Flask app, `admin_routes`, `api_endpoint`, `database`, `templates`, atd.). Co kam nahrát je popsáno v **CO_KAM_NAHRAT_A_UPRAVIT.md**. Při použití gitu to řešíte tím, že na PA máte naklonovaný ten samý repozitář a po `git pull` tam máte vždy aktuální verzi.

---

## 4. Heslo pro e-maily (SMTP Seznam)

Aby web mohl posílat e-maily (objednávky, aktivace, notifikace), musí na **PythonAnywhere** znát heslo k účtu **info@dokucheck.cz**. Heslo se **neukládá v kódu ani na Git** – zadáte ho jen na serveru.

**Kam heslo zadat:**

1. Přihlaste se na [pythonanywhere.com](https://www.pythonanywhere.com/) → záložka **Web**.
2. Klikněte na **vaši webovou aplikaci** (např. cieslar.pythonanywhere.com).
3. Sjeďte k sekci **"Environment variables"** (nebo "Code" → "Environment variables").
4. Do pole přidejte řádek (nahraďte `VASE_HESLO` skutečným heslem k info@dokucheck.cz – Heslo pro aplikace na Seznamu):
   ```
   MAIL_PASSWORD=VASE_HESLO
   ```
5. Klikněte na zelené **Save** a pak **Reload** webové aplikace.

**Kde se uloží:** Jen na PythonAnywhere u vaší web app v konfiguraci. Nikdy se neposílá do Gitu ani do repozitáře. Ostatní SMTP údaje (server, port, uživatel) jsou v kódu s výchozími hodnotami; heslo je vždy jen z proměnné prostředí.

---

## 5. Shrnutí

| Způsob | Co děláte vy | Automaticky |
|--------|----------------|-------------|
| **Jen Git** | Na PC: `git push`. Na PA: v Bash `git pull` a v Web záložce **Reload**. | – |
| **Deploy skript** | Na PC spustíte `python deploy_to_pythonanywhere.py`. | Commit + push, volitelně SSH `git pull`, **Reload** přes PA API. |

Doporučení: repozitář na GitHubu (nebo jinde), na PythonAnywhere jeden klon; verze archivujete tagy (`git tag`). Testované verze pushnete a na web je dostanete buď ručním `git pull` + Reload, nebo pomocí deploy skriptu včetně automatického Reloadu.

Odkaz na dokumentaci PythonAnywhere API (reload): [PythonAnywhere API – Reload Web App](https://help.pythonanywhere.com/pages/ReloadWebApp/).
