# Historie kontrol podle tieru (návrh)

## Tabulka check_history (PRO historie)

Používá se pro kartu „Historie“ na portálu. Záznamy se ukládají **pouze pro uživatele s tiery Pro** (vedoucí projektant).

### SQL tabulka

```sql
CREATE TABLE IF NOT EXISTS check_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,           -- api_key
    filename TEXT NOT NULL,
    status TEXT DEFAULT 'ok',        -- 'ok' | 'error'
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    results_json TEXT,               -- celý payload kontroly (viz níže)
    batch_id TEXT,                   -- volitelně, pokud šlo o dávku
    source TEXT,                     -- volitelně: 'agent' | 'web'
    FOREIGN KEY (user_id) REFERENCES api_keys(api_key)
);
```

### Struktura results_json

Stejná jako u `check_results.results_json` (celý objekt `result_data`), aby šlo v UI zobrazit stejný detail bez dvou různých parserů.

```json
{
  "file_name": "dokument.pdf",
  "file_path": "slozka/dokument.pdf",
  "relative_path": "slozka/dokument.pdf",
  "folder": "slozka",
  "file_hash": "...",
  "file_size": 12345,
  "processed_at": "2025-02-02T12:00:00",
  "success": true,
  "results": {
    "pdf_format": {
      "is_pdf_a3": true,
      "exact_version": "PDF/A-3b"
    },
    "signatures": [
      { "valid": true, ... }
    ]
  }
}
```

### API v database.py

- **save_check(user_id, data, batch_id=None, source=None)**  
  Uloží jeden záznam do `check_history` pouze pokud má uživatel tier **Pro**.  
  Vrací `(True, row_id)` nebo `(False, reason)`.

- **get_check_history(user_id, limit=100, offset=0)**  
  Vrátí seznam záznamů pro portál (včetně `parsed_results` z JSON).

- **delete_check_history_record(record_id, user_id)**  
  Smaže záznam jen pokud patří danému `user_id`.

---

## Cíl (původní návrh)
- **Free / Free trial**: Po přihlášení se zobrazí prázdné – žádná historie (nebo jen poslední běh).
- **Basic, Pro, Enterprise**: Na webu zůstane historie kontrol – uživatel vidí své minulé dávky po „Načíst výsledky“.

## Současný stav
- Po přihlášení/odhlášení se **v agentovi i na webu vymaže zobrazení** (fronta úkolů, výsledky). Data na serveru zůstávají (batche jsou ukládána podle `api_key`).
- Endpoint `/api/agent/results` vrací **všechny batche** (bez filtru podle přihlášeného uživatele).

## Jak to doplnit (vyšší verze)

1. **Web – posílat api_key při načítání**
   - Pokud je uživatel přihlášen (localStorage má `api_key`), volat např. `/api/agent/results?api_key=XXX` nebo posílat hlavičku `Authorization: Bearer XXX`.

2. **Server – filtr podle api_key**
   - V `get_agent_results()` brát volitelný parametr `api_key` (z query nebo z hlavičky).
   - Volat např. `db.get_agent_results_grouped(limit=50, api_key=api_key)`.
   - V databázi mít v `get_agent_results_grouped(api_key=None)` podporu filtru: pokud je `api_key` zadán, vracet jen batche s tímto `api_key`.

3. **Server – historie podle tieru**
   - Pro **Free (tier 0)**: při `api_key` Free uživatele vracet např. jen poslední 1 batch (nebo 0) – „žádná historie“.
   - Pro **Basic+ (tier 1, 2, 3)**: vracet všechny batche daného `api_key` (např. `limit=50` nebo víc) – **historie se nechává**.

4. **Volitelně – mazání historie pro Free při přihlášení**
   - Přidat endpoint např. `POST /api/agent/clear-my-history` (s Bearer api_key), který smaže batche a výsledky daného `api_key`. Web ho může volat po přihlášení jen pro Free tier, aby na serveru nezůstávala stará data.

## Shrnutí
- Jeden zdroj kódu: rozdíl je jen v tom, **co vrací** `get_agent_results_grouped(api_key, tier)` (limit 0 vs. všechny batche).
- Rozšíření: v `database.py` metoda `get_agent_results_grouped(limit, api_key=None)`; v `api_endpoint.py` číst `api_key` z requestu, zjistit tier a podle tieru omezit počet vrácených batchů.
