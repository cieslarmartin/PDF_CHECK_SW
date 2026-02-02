# PDF_CHECK_SW

Kořenová složka projektu PDF Check (Web + Agent).

## Struktura (po přesunu)

- **web_app/** – obsah z v42 (Flask, API, admin, šablony)
- **desktop_agent/** – agent pro kontrolu PDF (agent.py, ui.py, pdf_checker.py, license.py)
- **archived_signing_module/** – archiv modulu pro podepisování PDF (pdf_converter, pdf_converter_gui, …)

## Spuštění

- **Agent:** `cd desktop_agent` → `python pdf_check_agent_main.py`
- **Web:** Po zkopírování (viz níže): `cd web_app` → `python pdf_check_web_main.py`
- **Archiv podepisování:** Po zkopírování: `cd archived_signing_module` → `python pdf_converter_gui.py`

## Dokončení přesunu (web_app + archived_signing_module)

Z adresáře **PDF_DOKU_Final** spusťte jednou:

```text
python COPY_TO_PDF_CHECK_SW.py
```

Skript zkopíruje v42 → web_app (včetně přejmenování hlavního souboru) a modul podepisování → archived_signing_module.

## Dokumentace

- **ANALYZA_PRED_PRESUNEM.md** – provazby Agent ↔ Web, API, licence
- **UKLIZENO.md** – přehled „kde co leží“ po reorganizaci
