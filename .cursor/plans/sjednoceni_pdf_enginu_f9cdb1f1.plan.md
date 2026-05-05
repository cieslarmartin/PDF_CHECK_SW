---
name: Sjednoceni PDF enginu
overview: V izolované složce testovaci_engine/ postavit třetí (sjednocený) PDF engine a srovnávací runner, který vedle sebe pustí 3 enginy (web legacy, agent legacy, nový sjednocený) nad reálnou sadou PDF v testovaci_engine/zdrojove PDF_testovaci/. Výstup = HTML report s rozdíly. Dokud runner nedá zelenou, produkce ani agent se nesahají.
todos:
  - id: create-sandbox-folder
    content: Vytvořit v testovaci_engine/ strukturu (reports/, README.md, .gitkeep)
    status: pending
  - id: gitignore-fixtures
    content: Do .gitignore přidat testovaci_engine/zdrojove PDF_testovaci/**/*.pdf a testovaci_engine/reports/
    status: pending
  - id: shared-engine
    content: Vytvořit testovaci_engine/pdf_engine.py (věrná kopie desktop_agent/pdf_checker.py) + přidat analyze_from_bytes a get_pdfa_details
    status: pending
  - id: web-adapter
    content: Vytvořit testovaci_engine/pdf_engine_web.py (adaptér doplňující pdfVersion, pdfaConformance, pdfaLevel, tsa_qualified, display name)
    status: pending
  - id: compare-runner
    content: Napsat testovaci_engine/compare_engines.py se 3 enginy vedle sebe (A web legacy, B agent legacy, C nový sjednocený) a HTML reportem
    status: pending
  - id: run-parity
    content: Pustit runner nad všemi PDF v testovaci_engine/zdrojove PDF_testovaci/ a analyzovat rozdíly
    status: pending
  - id: promote-engine
    content: (Navazující fáze) Povýšit nový engine na produkční, přepojit web endpointy, odstranit duplicity v web_app/
    status: pending
  - id: deploy-pa
    content: (Navazující fáze) Nasadit na PythonAnywhere (git pull + reload), bez zásahu do agenta
    status: pending
isProject: false
---

# Sjednocení na jeden PDF engine

## Fázování

- **Fáze 1 (tento plán)**: všechno v izolované složce `testovaci_engine/`. Nulový zásah do `web_app/` i `desktop_agent/`. Cíl = HTML report dokazující, že **všechny 3 enginy dávají na reálné sadě PDF stejné výsledky**.
- **Fáze 2 (navazující, až bude runner zelený)**: povýšení nového enginu do produkce, přepojení webu, odstranění duplicit, deploy na PythonAnywhere.

## Struktura izolované složky

```
PDF_CHECK_SW/
  testovaci_engine/
    README.md                              jak spustit runner
    pdf_engine.py                          sdílený engine (věrná kopie desktop_agent/pdf_checker.py + 2 nové funkce)
    pdf_engine_web.py                      web adaptér (pdfVersion, pdfaConformance, pdfaLevel, tsa_qualified, name)
    compare_engines.py                     srovnávací runner se 3 enginy vedle sebe
    reports/                               výstupy runneru (HTML reporty, JSON snapshoty)
    zdrojove PDF_testovaci/                reálná PDF sada (212+ souborů), dodána uživatelem, do gitu nejde
  .gitignore                               doplnit: testovaci_engine/zdrojove PDF_testovaci/**/*.pdf, testovaci_engine/reports/
```

## Tři enginy vedle sebe

1. **Engine A – web legacy**: dynamicky naimportovaný z `web_app/pdf_check_web_main.py` (aktuální produkční webový engine, `analyze_pdf_from_content` + `_enrich_signatures_tsa_qualified`).
2. **Engine B – agent legacy**: naimportovaný z `desktop_agent/pdf_checker.py` (aktuální engine v distribuovaném exe, `analyze_pdf_file`, z wrapped výstupu se vezme `results`).
3. **Engine C – nový sjednocený**: `testovaci_engine/pdf_engine.py` + `testovaci_engine/pdf_engine_web.py`.
   - `pdf_engine.py` je na startu věrná kopie desktop enginu + 2 nové funkce:
     - `analyze_from_bytes(content: bytes) -> dict` (pro cestu web uploadu: bytes → tempfile → `analyze_pdf_file`),
     - `get_pdfa_details(content: bytes) -> dict` (vrací `pdf_version`, `pdfa_conformance`, `pdfa_level` – agent to nepotřebuje, web ano).
   - `pdf_engine_web.py` je adaptér, který výstup `pdf_engine` přizpůsobí tvaru, co dnes očekává web UI.
   - Žádné nové regexy na detekci podpisů/TSA/DocMDP – jen strukturní sjednocení, aby se jádro nezměnilo.

## Jak runner funguje

`python testovaci_engine/compare_engines.py`

Pro každé PDF v `testovaci_engine/zdrojove PDF_testovaci/` (rekurzivně):

1. Načte soubor z disku + načte ho jako `bytes`.
2. Zavolá **Engine A** (cesta web upload, `bytes`).
3. Zavolá **Engine B** (cesta agent, `path`) – vezme `results` část wrapped výsledku.
4. Zavolá **Engine C** oběma cestami (agent i web upload) a porovná, že **uvnitř nového enginu jsou obě cesty identické** (klíčová akceptační podmínka).
5. Porovná A, B, C na klíčových polích:
   - `pdfaVersion`, `pdfaStatus`, `pdfaLevel`, `pdfVersion`, `pdfaConformance`,
   - `sig`, `signer`, `ckait`, `tsa`,
   - `sig_count`, `signatures[*].{type, valid, signer, ckait, date, tsa, tsa_issuer, timestamp_valid, certificate_valid, tsa_qualified, name}`,
   - `docmdp_level`, `issr_compatible`.
6. Zapíše řádek do tabulky s barevným označením shody/rozdílu.

Runner končí nenulovým exit kódem, pokud je kdekoliv rozdíl (pro snadné zapojení do CI).

## Výstup = HTML report

Soubor `testovaci_engine/reports/compare_YYYY-MM-DD_HHMM.html` – statická stránka, otevře se dvojklikem v prohlížeči. Obsahuje:

- hlavičku se souhrnem: počet souborů, počet zcela shodných, počet s rozdílem,
- filtr „zobraz jen soubory s rozdílem“,
- tabulku: řádek = pole, sloupce = Engine A / B / C, barevné označení rozdílů,
- kliknutí na název souboru rozbalí plný JSON výstup všech 3 enginů (detail pro ladění),
- samostatnou sekci „Engine C: agent path vs web path“ (interní konzistence nového enginu).

Paralelně se uloží `reports/snapshots/<filename>.json` pro regresní srovnání mezi běhy.

## Akceptační kritérium Fáze 1

- Runner proběhne nad všemi fixtures.
- **Engine C: shoda cesty agent vs web uploadu = 100 % na všech souborech.** Toto je povinné.
- Engine C ≡ Engine B na všech polích, která oba vrací (Engine B nemá `pdfaLevel`/`pdfVersion`/`pdfaConformance`, to je známý dluh desktop enginu – Engine C je má navíc jako webovou nadstavbu, žádný rozdíl v detekci).
- Engine C ≡ Engine A na všech polích včetně web nadstavby.
- Odchylky A vs B jsou dokumentované (dnešní duální realita) – Engine C je slučuje.

Teprve po splnění jdeme do Fáze 2.

## Co udělá uživatel, co udělám já

- **Uživatel** (už hotovo): nakopíroval reálná PDF do `testovaci_engine/zdrojove PDF_testovaci/`.
- **Já** (ve Fázi 1, po Vašem OK):
  1. vytvořím strukturu v `testovaci_engine/`,
  2. doplním `.gitignore`,
  3. napíšu `pdf_engine.py` (kopie desktop + 2 funkce),
  4. napíšu `pdf_engine_web.py` (adaptér),
  5. napíšu `compare_engines.py` (runner + HTML report),
  6. pustím runner,
  7. nahlásím souhrn (kolik souborů shoda, kolik rozdíl, v kterých polích) a odkaz na HTML report.

## Fáze 2 – zapsáno pro úplnost, teď se neimplementuje

1. Přesunout ověřený `pdf_engine.py` do sdíleného místa (root projektu).
2. `desktop_agent/pdf_checker.py` ponechat jako re-export (`from pdf_engine import *`) – distribuovaný exe se tím nemění.
3. Web endpointy `/analyze`, `/analyze-batch`, `/api/scan-folder`, `/api/scan-folder-stream` → přepojit na `pdf_engine_web`.
4. Smazat duplicitní bloky z `web_app/pdf_check_web_main.py` (řádky cca 2754–3515).
5. Bump `WEB_BUILD` a poslední trojčíslí `WEB_VERSION` ve `web_app/version.py`. `desktop_agent/version.py` se nemění.
6. PythonAnywhere: git pull + WSGI reload, smoke test na 3 fixtures.
7. Rollback: jediný revert commit vrátí adaptér zpět – engine zůstává v `pdf_engine`.

## Co je explicitně mimo

- Žádná úprava `desktop_agent/` ve Fázi 1 i Fázi 2 (distribuovaný agent se nemění).
- Žádný zásah do produkčního webu ani do databáze.
- Žádné nové detekční regexy – jen strukturní sjednocení.
