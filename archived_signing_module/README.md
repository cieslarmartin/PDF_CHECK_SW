# Archiv modulu podepisování PDF

Tato složka je určena pro **rozpracovaný modul podepisování** (pdf_converter, pdf_converter_gui, profily PFX/TSA).

**Jak sem dostat soubory:** Z adresáře `PDF_DOKU_Final` spusťte:

```text
python COPY_TO_PDF_CHECK_SW.py
```

Skript zkopíruje z `pdfcheck_agent` sem:
- složku `pdf_converter/`
- soubory `pdf_converter_gui.py`, `config.json`, `signer_config.json`, `signer_config.yaml`

Po zkopírování nainstalujte závislosti: `pip install -r requirements.txt`
