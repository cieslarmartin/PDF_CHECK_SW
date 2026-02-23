# Výpis kódu a logika detekce ISSŘ (DocMDP) – tři cesty

Dokument slouží k nalezení „úzkého hrdla“ v konzistenci detekce zámku. **Žádná oprava, pouze výpis a popis.**

---

## CESTA 1: AGENT → WEB (metadata před odesláním)

### 1.1 Kde agent vytváří výsledek (desktop_agent)

**Soubor:** `desktop_agent/pdf_check_agent_main.py`

- Jednotlivý soubor: `_check_single_file(filepath)` volá `analyze_pdf_file(filepath)` a výsledek se pak posílá přes `send_results_to_api(result)` → `send_batch_results_to_api([result])`.
- Složka / více souborů: `analyze_folder` resp. `analyze_multiple_pdfs` vrací `results` (seznam), ten se posílá přes `send_batch_results_to_api(results, folder)`.

```python
# pdf_check_agent_main.py – relevantní úryvky

def _check_single_file(self, filepath):
    result = analyze_pdf_file(filepath)   # ← zde vzniká struktura
    return result

def send_results_to_api(self, result):
    self.send_batch_results_to_api([result], source_folder=None)

def send_batch_results_to_api(self, results, source_folder=None):
    out = self.license_manager.upload_batch(batch_name, source_folder, results)  # ← odeslání
```

**Otázka: Obsahuje JSON odesílaný na server pole `is_locked` nebo `mdp_level`?**

- Agent **neposílá** `is_locked` ani `mdp_level` jako samostatné top-level pole.
- Posílá se to, co vrací `analyze_pdf_file()` a co do payloadu vloží `license.upload_batch()`.

---

### 1.2 Struktura vrácená z `analyze_pdf_file` (desktop_agent/pdf_checker.py)

```python
# pdf_checker.py – návratová hodnota analyze_pdf_file (zkráceno)

return {
    'success': True,
    'file_name': filename,
    'file_hash': file_hash,
    'file_size': file_size,
    'processed_at': datetime.now().isoformat(),
    'results': {
        'pdf_format': pdf_format,
        'signatures': signatures,
        'file_info': {...},
        'docmdp_level': docmdp_level,    # ← int | None (1 = zamčeno)
        'issr_compatible': issr_compatible,  # ← bool
    },
    'display': {
        'pdf_version': ...,
        'is_pdf_a3': ...,
        'signature_count': ...,
        'signatures': ...,
        'docmdp_level': docmdp_level,
        'issr_compatible': issr_compatible,
    }
}
```

- **Pole pro ISSŘ:** `results.issr_compatible`, `results.docmdp_level`, `display.issr_compatible`, `display.docmdp_level`.
- **Žádné** pole `is_locked` ani `mdp_level` v této struktuře není (název je vždy `issr_compatible` / `docmdp_level`).

---

### 1.3 Co agent skutečně posílá na server (desktop_agent/license.py)

```python
# license.py – upload_batch

def upload_batch(self, batch_name, source_folder, results):
    files_data = []
    for r in results:
        if r.get('success'):
            files_data.append({
                'file_name': r.get('file_name'),
                'file_hash': r.get('file_hash'),
                'file_size': r.get('file_size'),
                'processed_at': r.get('processed_at'),
                'folder': r.get('folder', '.'),
                'relative_path': r.get('relative_path'),
                'results': r.get('results')   # ← POUZE klíč "results", ne celý objekt!
            })
    payload = {
        'batch_name': batch_name,
        'source_folder': source_folder,
        'total_files': len(files_data),
        'results': files_data
    }
    response = requests.post(f"{self.api_url}/api/batch/upload", json=payload, ...)
```

- Každá položka v `results` má tedy: `file_name`, `file_hash`, `file_size`, `processed_at`, `folder`, `relative_path`, **`results`** (vnořený objekt).
- **Do serveru se neposílá** `display` – posílá se jen `r.get('results')`, tedy objekt obsahující mj. `issr_compatible` a `docmdp_level`.
- **Shrnutí:** V JSONu od agenta **není** `is_locked` ani `mdp_level`; jsou tam **`results.issr_compatible`** a **`results.docmdp_level`**. Web by měl číst právě tato pole.

---

## CESTA 2: API / SERVER-SIDE (příjem a uložení metadat z Agenta)

### 2.1 Příjem batch uploadu (web_app/api_endpoint.py)

```python
# api_endpoint.py – route /api/batch/upload

@app.route('/api/batch/upload', methods=['POST'])
def upload_batch():
    data = request.get_json()
    batch_name = data.get('batch_name')
    source_folder = data.get('source_folder')
    results = data.get('results', [])   # ← seznam položek od agenta

    batch_id = db.create_batch(api_key, batch_name, source_folder)
    for result in results:
        success, _ = db.save_result(api_key, result, batch_id)   # ← result = jedna položka z payloadu
```

- Jedna položka `result` = přesně to, co agent poslal v jednom prvku `results`:  
  `{ file_name, file_hash, file_size, processed_at, folder, relative_path, results: { pdf_format, signatures, file_info, docmdp_level, issr_compatible } }`.
- **Žádné** přejmenování polí; server nečeká `is_locked` ani `mdp_level`, jen tato struktura.

---

### 2.2 Uložení do DB (web_app/database.py)

```python
# database.py – save_result

def save_result(self, api_key, result_data, batch_id=None):
    file_name = result_data.get('file_name')
    # ...
    results = result_data.get('results', {})   # ← vnitřní results
    pdf_format = results.get('pdf_format', {})
    signatures = results.get('signatures', [])
    # ...
    results_json = json.dumps(result_data, ensure_ascii=False)   # ← CELÝ result_data jako JSON
    cursor.execute(''' INSERT INTO check_results (..., results_json) VALUES (..., ?) ''', (..., results_json))
```

- Ukládá se **celý** `result_data** (jedna položka z payloadu agenta).
- V DB tedy v `results_json` je přesně:  
  `{ file_name, file_hash, file_size, processed_at, folder, relative_path, results: { ..., docmdp_level, issr_compatible } }`.
- **`display`** v uloženém JSONu **není**, protože ho agent v této cestě vůbec neposílá.

---

### 2.3 Vrácení výsledků pro web (web_app/api_endpoint.py + database.py)

```python
# get_agent_results vrací batches z db.get_agent_results_grouped(api_key=api_key)
# database.py – get_agent_results_grouped:
#   Pro každý batch: SELECT * FROM check_results WHERE batch_id = ?
#   Pro každý result: result['parsed_results'] = json.loads(result['results_json'])
#   batch['results'] = results  ← seznam řádků z check_results
```

- Každý prvek v `batch.results` je řádek z DB: obsahuje mj. `results_json`, `file_name`, `file_path`, `folder_path`, atd.
- Backend doplní **`parsed_results`** = rozparsovaný `results_json` (tedy původní `result_data` od agenta).
- Struktura v odpovědi pro frontend tedy je:
  - `r.parsed_results` = `{ file_name, file_hash, ..., results: { pdf_format, signatures, docmdp_level, issr_compatible } }`
  - **`r.parsed_results.results.issr_compatible`** a **`r.parsed_results.results.docmdp_level`** jsou k dispozici.
  - **`r.parsed_results.display`** u dat z agenta **neexistuje** (nebylo odesláno).

---

### 2.4 Jak je zpracováváš a ukládáš – shrnutí

| Krok | Co se děje |
|------|------------|
| Příjem | Jedna položka = `{ file_name, ..., results: { ..., issr_compatible, docmdp_level } }`. Bez `display`. |
| Uložení | Celý tento objekt se ukládá do `check_results.results_json`. |
| Pro UI | Při čtení se z `results_json` vytvoří `parsed_results`; ISSŘ je v `parsed_results.results.issr_compatible`. |

---

## CESTA 3: PŘÍMÝ WEB UPLOAD (drag & drop v prohlížeči)

### 3.1 Jedno PDF – endpoint /analyze (web_app/pdf_check_web_main.py)

```python
@app.route('/analyze', methods=['POST'])
def analyze():
    file = request.files['file']
    content = file.read()
    # ...
    return jsonify(analyze_pdf_from_content(content))
```

### 3.2 Batch upload – endpoint /analyze-batch

```python
@app.route('/analyze-batch', methods=['POST'])
def analyze_batch():
    files = request.files.getlist('files') or ...
    for file in files:
        content = file.read()
        r = analyze_pdf_from_content(content)
        r['filename'] = file.filename
        results.append(r)
    return jsonify({'results': results, 'count': len(results)})
```

- U obou cest se používá **`analyze_pdf_from_content(content)`** – tedy analýza z bajtů (bez cesty k souboru).

---

### 3.3 Analýza z obsahu – použitá logika (web_app/pdf_check_web_main.py)

```python
def analyze_pdf_from_content(content):
    result = analyze_pdf(content)   # ← 1) nejdřív byte-scan (detect_docmdp_lock)
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        docmdp_reader = detect_docmdp_lock_via_reader(reader)
        result['docmdp_level'] = docmdp_reader['level']
        result['issr_compatible'] = not docmdp_reader['locked']
    except Exception:
        pass
    return result
```

- **Ano**, při přímém uploadu se používá hloubková logika: **PdfReader(io.BytesIO(content))** + **`detect_docmdp_lock_via_reader(reader)`**, která uvnitř volá **`is_pdf_locked_for_issr(reader)`**.
- Ta kontroluje:
  - **SigFieldLock:** pole `/Sig` v `/AcroForm`/`/Fields`, u každého pole `/Lock` a v něm **`/P == 1`**,
  - **Signature Reference / TransformParams:** u každého podpisu `/V` → `/Reference` → u každé reference **`/TransformParams`** a v nich **`/P == 1`**.

Pokud pypdf vyhodí výjimku (poškozený PDF, nestandardní struktura), zůstane pouze byte-scan z `analyze_pdf(content)` a detekce může být nespolehlivá.

---

### 3.4 Hloubková detekce na webu (stejná jako v testovacím skriptu)

```python
def is_pdf_locked_for_issr(reader):
    catalog = reader.trailer.get("/Root") or getattr(reader, "root_object", None)
    catalog = _resolve_obj(catalog, reader)
    if not catalog or "/AcroForm" not in catalog:
        return False
    acro = catalog["/AcroForm"]
    acro = _resolve_obj(acro, reader)
    fields = acro["/Fields"] or []
    for f_ref in fields:
        f = _resolve_obj(f_ref, reader)
        if (str(f.get("/FT")) if f else "") != "/Sig":
            continue
        # 1) Přímý zámek pole (SigFieldLock)
        lock = f.get("/Lock")
        if lock is not None:
            lock = _resolve_obj(lock, reader)
            if lock is not None and int(lock.get("/P")) == 1:
                return True
        # 2) TransformParams v /V -> /Reference
        v = f.get("/V")
        v_dict = _resolve_obj(v, reader)
        for r in (v_dict.get("/Reference") or []):
            r_obj = _resolve_obj(r, reader)
            params = r_obj.get("/TransformParams")
            params = _resolve_obj(params, reader)
            if params is not None and int(params.get("/P")) == 1:
                return True
    return False
```

- Web tedy **používá stejnou hloubkovou logiku** (/Lock, /P 1, /TransformParams) jako v testovacím skriptu.
- **Možné důvody nespolehlivosti při přímém uploadu:**
  1. **Výjimka v pypdf** (nestandardní PDF, velký soubor, poškozený stream) → zůstane jen byte-scan, který může selhat.
  2. **Byte-scan** (`detect_docmdp_lock(content)`) hledá `/P 1` jen v okně 3500 bajtů za `/DocMDP`; u indirect referencí nebo složitější struktury může `/P` v tom okně chybět.
  3. **Jiná varianta zámku** (např. jiné umístění `/P` nebo jiný typ reference), kterou současná hloubková logika neprohlíží.

---

## PROČ WEB NEROZPOZNÁ ZÁMĚK, KDYŽ MU AGENT POŠLE METADATA?

- **Názvy polí:** Agent neposílá `is_locked` ani `mdp_level`. Posílá **`results.issr_compatible`** a **`results.docmdp_level`**. Server to ukládá beze změny.
- **Chyba je na frontendu** při zobrazení výsledků z agenta („Načíst výsledky“):

```javascript
// pdf_check_web_main.py (vložený JS) – loadAgentResults, mapování souborů z batch.results
const files = (batch.results || []).map(r => {
    const parsed = r.parsed_results || {};
    const pdfFormat = parsed.results?.pdf_format || {};
    const signatures = parsed.results?.signatures || [];
    // ...
    const issr = (r.results && r.results.issr_compatible) !== false && (!r.display || r.display.issr_compatible !== false);
    return { ..., issr_compatible: issr };
});
```

- **`r`** = jeden záznam z API: má klíče z DB řádku (`file_name`, `file_path`, `folder_path`, **`parsed_results`**, …).
- V odpovědi API **není** `r.results` ani `r.display` – to jsou klíče **uvnitř** uloženého JSONu, tedy v **`r.parsed_results`**.
- Správně by mělo být: **`parsed.results.issr_compatible`** (a případně `parsed.display.issr_compatible`, ale u dat z agenta `display` neexistuje).
- Protože `r.results` je `undefined`, výraz `(r.results && r.results.issr_compatible) !== false` se vyhodnotí jako `(undefined !== false)` = **true**. A `!r.display` je také true. Výsledek: **issr se vždy bere jako true** a web zámek nerozpozná, i když agent poslal `issr_compatible: false`.

**Závěr:** Web nerozpozná zámek u dat z agenta proto, že čte **špatnou úroveň objektu** (`r.results` / `r.display` místo `r.parsed_results.results` resp. `r.parsed_results.display`).

---

## PROČ JE DETEKCE PŘI PŘÍMÉM NAHRÁNÍ JEN ČÁSTEČNÁ?

- **Použitá logika:** Přímý upload používá stejnou hloubkovou detekci (SigFieldLock + TransformParams v Reference) jako testovací skript.
- **Možné příčiny nespolehlivosti:**
  1. **Fallback na byte-scan:** Když `PdfReader(io.BytesIO(content))` nebo `detect_docmdp_lock_via_reader` selže (exception), výsledek zůstane z `analyze_pdf(content)` – tedy jen byte-scan. Ten může u řady PDF hlásit „OK“.
  2. **Byte-scan** nepokrývá případy, kdy je `/P 1` v indirect objektech nebo mimo 3,5 kB okno za `/DocMDP`.
  3. **Typy zámků:** Současný kód explicitně kontroluje:
     - zámek na **poli podpisu** (`/Sig` → `/Lock` → `/P 1`),
     - **Reference** podpisu (`/V` → `/Reference` → `/TransformParams` → `/P 1`).  
     Pokud existuje jiná varianta (např. DocMDP jen v kořeni katalogu bez AcroForm, nebo jiná struktura), kód ji může přehlížet.

---

## Shrnutí toků

| Cesta | Kde vzniká ISSŘ | Co se odesílá/ukládá | Kde se může ztratit |
|------|------------------|----------------------|----------------------|
| Agent → Web | `pdf_checker.analyze_pdf_file` → `results.issr_compatible`, `display.issr_compatible` | Agent posílá jen `results` (včetně `issr_compatible`, `docmdp_level`). Server ukládá celý payload do `results_json`. | **Frontend** čte `r.results` a `r.display` místo `r.parsed_results.results` → ISSŘ vždy „OK“. |
| Přímý upload | `analyze_pdf_from_content` → PdfReader + `detect_docmdp_lock_via_reader` | Vrací přímo objekt s `issr_compatible`, `docmdp_level`. | Výjimka v pypdf → zůstane byte-scan; nebo nestandardní zámek. |

Tím je popsáno „úzké hrdlo“: **zobrazení výsledků z agenta na webu čte ISSŘ z nesprávné úrovně objektu (`r` místo `r.parsed_results`).**
