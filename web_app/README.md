# PDF Check Web

Flask webová aplikace pro zobrazení výsledků kontroly PDF a správu licencí.

**Jak sem dostat soubory:** Z adresáře `PDF_DOKU_Final` spusťte:

```text
python COPY_TO_PDF_CHECK_SW.py
```

Skript zkopíruje obsah složky `v42` sem a přejmenuje hlavní soubor na `pdf_check_web_main.py`.

**Spuštění:**  
`python pdf_check_web_main.py`  
(nebo `python pdf_dokucheck_pro_v41_with_api.py` před přejmenováním)

**Závislosti:**  
`pip install -r requirements.txt`

Databáze SQLite (`pdfcheck_results.db`) se vytvoří v této složce při prvním spuštění.
