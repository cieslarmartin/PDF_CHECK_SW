# Lokální testování

## 1. Web v prohlížeči (upload PDF, dashboard)

Z **kořene projektu** (`c:\Claude\PDF_CHECK_SW`):

```powershell
python run_local.py
```

- V prohlížeči otevři: **http://127.0.0.1:8080** (pouze HTTP, ne https).
- Nahraj PDF přes „Serverová / Cloudová kontrola“ a spusť analýzu.
- Pro ukončení serveru: **CTRL+C** v terminálu.

## 2. Kontrola PDF bez webu (jen logika, žádný Flask)

Z **kořene projektu**:

**Jedno PDF (zadej cestu):**
```powershell
python local_test/run_check.py "c:\cesta\k\soubor.pdf"
```

**Všechna PDF ve složce `local_test/pdfs/`:**
- Zkopíruj PDF do složky `local_test/pdfs/`.
- Spusť:
```powershell
python local_test/run_check.py
```

Výstup: počet podpisů, typ (Časové razítko / Podpis), jméno. Žádný web, žádný port.

## 3. Co nepoužívat při lokálním testu

- **https://127.0.0.1:8080** – způsobí SSL chybu. Pouze **http://127.0.0.1:8080**.
- Spouštění `python web_app/pdf_check_web_main.py` na portu 5000 – může kolidovat s jinými službami; pro test použij `run_local.py` na 8080.
