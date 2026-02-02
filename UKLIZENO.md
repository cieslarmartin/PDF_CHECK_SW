# PDF_CHECK_SW – UKLIZENO

Reorganizace dokončena. Přehled, kde co leží a co je potřeba dořešit.

---

## DŮLEŽITÉ: Dokončení kopírování

Terminál v tomto prostředí nemá přístup k oběma cestám najednou. **Pro dokončení přesunu** spusťte na svém PC (z adresáře `PDF_DOKU_Final`):

```text
cd C:\Claude\PDF_DOKU_Final
python COPY_TO_PDF_CHECK_SW.py
```

Skript:
1. Zkopíruje **v42** → **PDF_CHECK_SW\web_app**
2. Přejmenuje v web_app soubor `pdf_dokucheck_pro_v41_with_api.py` na `pdf_check_web_main.py`
3. Zkopíruje modul podepisování z **pdfcheck_agent** → **PDF_CHECK_SW\archived_signing_module** (pdf_converter/, pdf_converter_gui.py, config.json, signer_config.*)

---

## Kde co teď leží

### Kořen: `C:\Claude\PDF_CHECK_SW\`

| Položka | Popis |
|--------|--------|
| **README.md** | Popis struktury projektu |
| **ANALYZA_PRED_PRESUNEM.md** | Analýza provazeb Agent ↔ Web |
| **UKLIZENO.md** | Tento soubor – přehled po úklidu |
| **COPY_TO_PDF_CHECK_SW.py** | *Je v PDF_DOKU_Final – spusťte odtud.* |

---

### `desktop_agent/` – Agent pro kontrolu PDF

| Soubor | Popis |
|--------|--------|
| **pdf_check_agent_main.py** | Hlavní vstupní bod (přejmenovaný z agent.py) |
| **ui.py** | GUI (tkinter, fronta úkolů, přihlášení) |
| **pdf_checker.py** | Logika kontroly PDF (PDF/A, podpisy, ČKAIT, TSA) |
| **license.py** | Licence – API klíč, přihlášení e-mailem, upload batch |
| **config.yaml** | Konfigurace (api.url, api.key, agent.auto_send) |
| **config.bez_klice.yaml** | Šablona configu bez klíče |
| **requirements.txt** | requests, PyYAML, tkinterdnd2 |

**Spuštění:**  
`cd desktop_agent` → `python pdf_check_agent_main.py`

**Config:**  
`config.yaml` se hledá v `_get_base_path()` = složka, kde leží `pdf_check_agent_main.py`, tedy `desktop_agent/config.yaml`. ✅

**Importy:**  
Všechny moduly (pdf_checker, license, ui) jsou ve stejné složce – žádná úprava importů není potřeba. ✅

---

### `web_app/` – Webová aplikace (Flask)

*Plný obsah sem doplní skript COPY_TO_PDF_CHECK_SW.py (zkopíruje z v42).*

| Po zkopírování | Popis |
|----------------|--------|
| **pdf_check_web_main.py** | Hlavní Flask aplikace (přejmenováno z pdf_dokucheck_pro_v41_with_api.py) |
| **api_endpoint.py** | API (auth, batch, license, agent results) |
| **database.py** | SQLite (api_keys, batches, check_results, …) |
| **license_config.py** | Tiery, feature flags, limity |
| **feature_manager.py** | Feature flags podle api_key |
| **admin_routes.py** | Admin (přihlášení, správa licencí) |
| **templates/** | admin_*.html |
| **requirements.txt** | Flask, openpyxl |

**Spuštění:**  
`cd web_app` → `python pdf_check_web_main.py`

**Databáze:**  
`database.py` používá `db_path='pdfcheck_results.db'` (relativní). Při spuštění z `web_app/` se DB vytvoří v `web_app/pdfcheck_results.db`. ✅

**Importy:**  
Všechny moduly (api_endpoint, database, license_config, feature_manager, admin_routes) jsou ve stejné složce – po přesunu z v42 zůstávají importy platné. ✅

---

### `archived_signing_module/` – Archiv modulu podepisování

*Plný obsah sem doplní skript COPY_TO_PDF_CHECK_SW.py (zkopíruje z pdfcheck_agent).*

| Po zkopírování | Popis |
|----------------|--------|
| **pdf_converter/** | Balíček: signer.py, cert_validator.py, config_manager.py, batch_processor.py, pdfa_converter.py, signature_remover.py, … |
| **pdf_converter_gui.py** | GUI pro konvertor a podepisování |
| **config.json** | Profily PFX a TSA |
| **signer_config.json**, **signer_config.yaml** | Konfigurace podepisování |
| **requirements.txt** | pyhanko, pikepdf, cryptography, tkinterdnd2, … |

**Spuštění konvertoru:**  
`cd archived_signing_module` → `python pdf_converter_gui.py`

---

## Ověření cest (Úkol 4)

| Komponenta | Cesta / proměnná | Kam míří po přesunu |
|------------|------------------|----------------------|
| **Agent – config** | `_get_config_path()` = `os.path.join(_get_base_path(), 'config.yaml')` | `desktop_agent/config.yaml` ✅ |
| **Agent – base path** | `_get_base_path()` = `dirname(abspath(__file__))` | `desktop_agent/` ✅ |
| **Web – databáze** | `Database(db_path='pdfcheck_results.db')` | `web_app/pdfcheck_results.db` při běhu z web_app ✅ |

Žádné absolutní cesty k v42 nebo pdfcheck_agent v kódu nejsou – po zkopírování a spuštění z příslušné složky vše míří na správná místa.

---

## Shrnutí

- **desktop_agent** – hotovo (soubory zkopírovány, přejmenován hlavní soubor na `pdf_check_agent_main.py`, requirements doplněn).
- **web_app** – struktura a requirements připraveny; obsah v42 sem zkopírujte spuštěním `COPY_TO_PDF_CHECK_SW.py` z `PDF_DOKU_Final`.
- **archived_signing_module** – struktura a requirements připraveny; obsah modulu podepisování sem zkopírujte stejným skriptem.

Po spuštění skriptu bude projekt **PDF_CHECK_SW** uzavřen jako „UKLIZENO“ a přenositelný (každá složka má vlastní `requirements.txt`).
