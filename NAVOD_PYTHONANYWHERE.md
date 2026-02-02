# Návod: Nasazení PDF Check Web na PythonAnywhere (PA)

Kompletní postup pro nasazení aplikace ze složky `web_app` na PythonAnywhere.

---

## Úkol 1: Struktura složek na PA

Na PythonAnywhere máte domovský adresář typu `/home/tvoje_jmeno/`. Doporučená struktura:

```
/home/tvoje_jmeno/
  web_app/                    ← sem nahrajete obsah z PDF_CHECK_SW/web_app
    pdf_check_web_main.py     ← hlavní Flask aplikace
    api_endpoint.py
    database.py
    license_config.py
    feature_manager.py
    admin_routes.py
    wsgi_pythonanywhere.py    ← WSGI konfigurace (nebo vložíte do záložky Web)
    requirements.txt
    templates/
      admin_login.html
      admin_dashboard.html
      admin_change_password.html
      admin_setup.html
    pdfcheck_results.db       ← vytvoří se při prvním spuštění (SQLite)
    static/                   ← volitelně; viz Úkol 4
```

**Jak tam dostat soubory:**
- Nahrajte ZIP vytvořený skriptem `create_deploy_zip.py` (z kořene PDF_CHECK_SW), pak na PA v Bash konzoli: `unzip web_app_deploy.zip -d ~/web_app`.
- Nebo nahrajte soubory přes Files (upload jednotlivě / složky).
- Nebo `git clone` z vašeho repozitáře a zkopírujte jen složku `web_app` do `~/web_app`.

---

## Úkol 2: WSGI configuration file

PythonAnywhere potřebuje WSGI soubor, který načte vaši Flask aplikaci. Máte dvě možnosti:

### A) Soubor `wsgi_pythonanywhere.py` v projektu

V `web_app` je soubor **`wsgi_pythonanywhere.py`**. Na PA v záložce **Web** → **WSGI configuration file** zadejte cestu:

```text
/home/tvoje_jmeno/web_app/wsgi_pythonanywhere.py
```

(Nahraďte `tvoje_jmeno` svým uživatelským jménem na PA.)

### B) Vložení kódu přímo do záložky Web

V záložce **Web** klikněte na odkaz k **WSGI configuration file** a do souboru vložte tento kód (a upravte cestu, pokud potřebujete):

```python
import sys
import os

# Cesta k složce web_app (nahraďte tvoje_jmeno!)
path = '/home/tvoje_jmeno/web_app'
if path not in sys.path:
    sys.path.insert(0, path)

os.chdir(path)

from pdf_check_web_main import app as application
```

Důležité:
- Hlavní soubor je **`pdf_check_web_main.py`**.
- Objekt aplikace v něm je **`app`**; PA vyžaduje proměnnou **`application`**, proto `app as application`.
- `sys.path` musí směřovat do složky, kde leží `pdf_check_web_main.py` (tedy do `web_app`).

Po úpravě WSGI souboru klikněte na **Reload** (zelené tlačítko u vaší domény).

---

## Úkol 3: Virtualenv a cesty v záložce Web

### 3.1 Virtuální prostředí a instalace závislostí (Bash konzole na PA)

V **Bash** konzoli na PythonAnywhere spusťte (nahraďte `tvoje_jmeno`):

```bash
cd ~/web_app
python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
```

Pokud PA nabízí jinou verzi Pythonu (např. 3.11), použijte ji:

```bash
python3.11 -m venv venv
```

Ověření:

```bash
source ~/web_app/venv/bin/activate
pip list
deactivate
```

### 3.2 Cesty v záložce „Web“

V záložce **Web** vyplňte:

| Pole | Hodnota |
|------|--------|
| **Source code** | `/home/tvoje_jmeno/web_app` |
| **Working directory** | `/home/tvoje_jmeno/web_app` |
| **WSGI configuration file** | `/home/tvoje_jmeno/web_app/wsgi_pythonanywhere.py` |
| **Virtualenv** | `/home/tvoje_jmeno/web_app/venv` |

(Nahraďte `tvoje_jmeno` svým PA uživatelským jménem.)

- **Source code** = kořen složky s kódem (kde je `pdf_check_web_main.py`).
- **Working directory** = stejná složka, aby SQLite vytvořil `pdfcheck_results.db` v `web_app` a relativní cesty fungovaly.
- **Virtualenv** = cesta k adresáři `venv` (bez `/bin/python`).

Po změnách vždy klikněte na **Reload** u vaší webové aplikace.

---

## Úkol 4: Statické soubory (CSS, obrázky)

V aktuálním projektu **`web_app` nemá složku `static`**. Aplikace používá vložené styly v šabloně (např. `HTML_TEMPLATE` v `pdf_check_web_main.py`) a šablony v `templates/`. Pro současnou verzi tedy **nastavování `/static/` na PA není nutné**.

Pokud později přidáte vlastní CSS nebo obrázky:

1. V `web_app` vytvořte složku **`static`** (např. `static/css`, `static/img`).
2. V záložce **Web** na PA v sekci **Static files** přidejte záznam:
   - **URL:** `/static/`
   - **Directory:** `/home/tvoje_jmeno/web_app/static`

Bez této složky a záznamu aplikace běží; přidáte je až při použití statických souborů.

---

## Úkol 5: ZIP pro nasazení

V kořeni projektu **PDF_CHECK_SW** je skript **`create_deploy_zip.py`**. Spusťte (z kořene PDF_CHECK_SW):

```text
cd C:\Claude\PDF_CHECK_SW
python create_deploy_zip.py
```

Vytvoří se soubor **`web_app_deploy.zip`** v `PDF_CHECK_SW` s obsahem složky `web_app` včetně:
- všech `.py` souborů včetně `pdf_check_web_main.py` a `wsgi_pythonanywhere.py`,
- `requirements.txt`,
- složky `templates/`,
- vybraných dokumentačních/config souborů,

a **bez**:
- `__pycache__`, `*.pyc`,
- složky `zaloha_pred_filtry`,
- velkých nebo zbytečných souborů (dle skriptu).

Tento ZIP nahrajte na PA (Files → Upload). V Bash konzoli pak:

```bash
mkdir -p ~/web_app
cd ~
unzip -o web_app_deploy.zip -d web_app
```

ZIP obsahuje soubory v kořeni archivu (bez složky `web_app`), takže `-d web_app` umístí `pdf_check_web_main.py`, `templates/`, atd. přímo do `~/web_app`.

---

## Shrnutí kroků na PA

1. Nahrát obsah `web_app` do `/home/tvoje_jmeno/web_app` (ZIP nebo ručně).
2. V Bash: vytvořit virtualenv a nainstalovat `pip install -r requirements.txt` (viz 3.1).
3. V záložce Web: nastavit Source code, Working directory, WSGI file, Virtualenv (viz 3.2).
4. Zkontrolovat WSGI: import z `pdf_check_web_main` a `app as application`.
5. Kliknout na **Reload**.
6. Volitelně: přidat `/static/` až když budete mít složku `static` a statické soubory.

Po prvním načtení stránky se v `web_app` vytvoří soubor **`pdfcheck_results.db`** (SQLite), pokud ho tam ještě nemáte.
