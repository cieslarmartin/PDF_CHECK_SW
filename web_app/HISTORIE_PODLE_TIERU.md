# Historie kontrol podle tieru (návrh)

## Cíl
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
