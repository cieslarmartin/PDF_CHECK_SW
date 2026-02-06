# Analýza: Na webu se po odeslání z trial zobrazí cieslarm@seznam.cz

## Problém

Uživatel v aplikaci (agent) používá **trial licenci zdarma**, odešle data na server a klikne na „Web“. V prohlížeči se otevře webová aplikace, ale je **přihlášen cieslarm@seznam.cz** místo trial účtu. Po odhlášení v agentovi by na webu neměl být žádný jiný uživatel.

## Možné příčiny (root cause)

### 1. Token se na serveru „nenajde“ → zůstane stará session (hlavní příčina)

**Tok:**
1. Agent (přihlášen jako trial) pošle data, pak získá přihlašovací URL: `POST /api/auth/one-time-login-token` s hlavičkou `Authorization: Bearer <trial_api_key>`.
2. Server vygeneruje jednorázový token a uloží ho do **paměti** (`_one_time_login_tokens` v `api_endpoint.py`).
3. Agent otevře v prohlížeči URL: `https://.../auth/from-agent-token?login_token=XXX`.
4. Požadavek přijde na web. **Pokud běží více workerů (procesů)**, může ho obsloužit **jiný proces** než ten, který token vytvořil. V tom procesu je slovník `_one_time_login_tokens` **prázdný** (paměť není sdílená mezi procesy).
5. `consume_one_time_token(token)` vrátí `(None, None)` → token „není platný“.
6. Původní kód pouze přesměroval na `/app` **bez změny session** → v prohlížeči zůstala **předchozí session** (např. cieslarm@seznam.cz z dřívějšího přihlášení na webu).

**Závěr:** Jednorázové tokeny byly uloženy jen v paměti jednoho procesu. Při více workerech (PythonAnywhere, gunicorn s N workers) token v druhém procesu neexistuje → přihlášení z tokenu selže → uživatel zůstane „přihlášen“ podle staré session.

### 2. V prohlížeči už byla stará session (cieslarm)

Uživatel se dříve na webu přihlásil ručně jako cieslarm@seznam.cz. Session (cookie) v prohlížeči to pamatuje. Když pak otevře odkaz z agenta a token se z výše uvedeného důvodu „nenajde“, kód pouze přesměruje na `/app` a session nezmění → zobrazí se cieslarm.

### 3. (Méně pravděpodobné) Agent používá jiný klíč než trial

Pokud v `config.yaml` zůstal starý API klíč (např. cieslarm) a uživatel v daném běhu **neklikl** na „Vyzkoušet zdarma“, agent používá ten uložený klíč. Pak by batch i přihlašovací odkaz byly pod cieslarm. V takovém případě by na webu byl cieslarm „správně“ z hlediska serveru (klíč byl cieslarm). Problém by byl v tom, že uživatel myslel, že je v režimu trial. Po kliknutí na „Vyzkoušet zdarma“ se ukládá trial klíč do configu i do paměti, takže oba requesty (upload batch a one-time-login-token) pak používají trial klíč.

## Opatření (aby se to neopakovalo)

1. **Při neplatném/chybějícím tokenu vždy zrušit přihlášení (session)**  
   V `auth_from_agent_token`: pokud `login_token` chybí nebo `consume_one_time_token` vrátí `(None, None)`, před přesměrováním na `/app` volat `session.pop('portal_user', None)`. Tím se nikdy „nedědí“ stará session (cieslarm) – uživatel uvidí nepřihlášený stav.

2. **Ukládat jednorázové tokeny do databáze**  
   Místo slovníku v paměti (`_one_time_login_tokens`) ukládat tokeny do tabulky v SQLite (nebo jiné sdílené úložiště). Všechny workery pak token najdou a přihlášení z odkazu z agenta bude fungovat bez ohledu na to, který proces request obslouží.

3. **Před nastavením nové session z tokenu vždy odstranit starou**  
   Před `session['portal_user'] = {...}` volat `session.pop('portal_user', None)`, aby v session nezůstaly staré klíče od předchozího uživatele.

## Soubory k úpravě

- `web_app/pdf_check_web_main.py` – `auth_from_agent_token`: session.pop při neplatném tokenu a před nastavením nové session (již provedeno).
- `web_app/api_endpoint.py` – vytváření tokenu: ukládat do DB; `consume_one_time_token`: číst a mazat z DB.
- `web_app/database.py` – tabulka `one_time_login_tokens`, metody `store_one_time_login_token`, `consume_one_time_login_token`.
