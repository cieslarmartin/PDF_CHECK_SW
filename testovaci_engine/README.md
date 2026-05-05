# Testovaci Engine

Offline porovnani 3 PDF enginu nad realnymi testovacimi PDF:

- `web legacy` (`web_app/pdf_check_web_main.py`)
- `agent legacy` (`desktop_agent/pdf_checker.py`)
- `unified new` (`testovaci_engine/pdf_engine.py` + `pdf_engine_web.py`)

## Spusteni

Z rootu projektu:

`python testovaci_engine/compare_engines.py`

Volitelne omezeni poctu:

`python testovaci_engine/compare_engines.py --limit 50`

## Vystup

- Terminal: prubeh + souhrn
- HTML report: `testovaci_engine/reports/compare_YYYY-MM-DD_HHMM.html`
- JSON snapshoty: `testovaci_engine/reports/snapshots/*.json`
