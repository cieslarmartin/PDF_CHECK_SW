# Co kam nahrát a co upravit – web + agent

Přehled **změněných souborů** a **co kam nahrát / upravit**, aby vše fungovalo na webu (PythonAnywhere) a u vás v agentovi.

---

## 1. WEB (PythonAnywhere) – které soubory se změnily a co nahrát

### Změněné soubory (nahrajte je na server a přepište stávající)

| Soubor | Kde je u vás | Kam na webu (typická cesta) |
|--------|----------------|-----------------------------|
| **admin_routes.py** | `41/admin_routes.py` | Projektová složka (např. `/home/USERNAME/cieslar.pythonanywhere.com/admin_routes.py` nebo tam, kde máte v41) |
| **templates/admin_dashboard.html** | `41/templates/admin_dashboard.html` | `templates/admin_dashboard.html` v téže projektové složce |

**Co se v nich změnilo:**
- **admin_routes.py** – při vytváření a úpravě licence se správně bere a ukládá typ licence (tier 0–3), včetně ošetření neplatných hodnot.
- **admin_dashboard.html** – oprava výběru typu licence při vytváření i editaci (select tier), odesílání tieru v obou formulářích, ošetření `None` v šabloně.

### Ostatní soubory webu (41)

Tyto soubory jsme **neměnili**; pokud je už na PythonAnywhere máte, nemusíte je znovu nahrávat kvůli těmto úpravám:

- `pdf_dokucheck_pro_v41_with_api.py`
- `api_endpoint.py`
- `database.py`
- `license_config.py`
- `feature_manager.py`
- `cieslar_pythonanywhere_com_wsgi.py`
- `init_test_data.py`
- `templates/admin_login.html`
- `templates/admin_setup.html`

### Co na webu udělat po nahrání

1. **Nahrát** výše uvedené dva soubory (přepsat stávající na serveru).
2. **Struktura složek** na serveru musí odpovídat v41:  
   - kořen projektu = složka s `pdf_dokucheck_pro_v41_with_api.py`, `admin_routes.py`, …  
   - vedle toho složka **templates** s `admin_dashboard.html`, `admin_login.html`, `admin_setup.html`.
3. **WSGI** (např. `cieslar_pythonanywhere_com_wsgi.py`) – pokud už ukazuje na správný soubor aplikace a složku projektu, nic neměňte.
4. **Restart webové aplikace** v záložce Web na PythonAnywhere (tlačítko Reload / Restart).

---

## 2. AGENT (váš počítač) – které soubory se změnily a co upravit

### Změněné soubory (jen dokumentace / ukázka, ne běh aplikace)

| Soubor | Kde je | Potřeba nahrát někam? |
|--------|--------|------------------------|
| **config.localhost.yaml** | `pdfcheck_agent/config.localhost.yaml` | Ne – je to jen ukázka. Na web se nenahazuje. |
| **QUICK_START.txt** | `pdfcheck_agent/QUICK_START.txt` | Ne – jen návod u vás v PC. |

**Kód agenta** (agent.py, license.py, ui.py, pdf_checker.py, config.yaml) jsme **neměnili**. Agent funguje s tím, co už máte.

### Co u agenta opravdu upravit (aby fungoval s webem)

Pouze **config.yaml** ve složce agenta:

```yaml
agent:
  auto_send: true
  show_results_window: true
api:
  url: https://cieslar.pythonanywhere.com
  key: VAS_API_KLIC_Z_ADMINU
```

- **api.url** – musí zůstat **https://cieslar.pythonanywhere.com** (ne 127.0.0.1).
- **api.key** – z adminu na webu: přihlášení → Nová licence (nebo existující) → zkopírovat API klíč a vložit sem.

Klíč můžete zadat i v agentovi přes „Nastavení API“; důležité je mít na webu správnou URL a platný klíč z licence.

---

## 3. Shrnutí – co kam

| Kde | Co udělat |
|-----|-----------|
| **PythonAnywhere (web)** | Nahrajte **admin_routes.py** a **templates/admin_dashboard.html** z složky 41, přepište stávající soubory. Restartujte webovou aplikaci. |
| **Agent (PC)** | Upravte jen **config.yaml**: `api.url: https://cieslar.pythonanywhere.com`, `api.key: <klíč z adminu>`. Žádné nahrávání na server. |

---

## 4. Návod na testování

Po nahrání a úpravách:  
**`41/TEST_FLOW_AGENT_WEB.md`** – tam je krok za krokem, jak testovat (admin → licence → agent → výsledky na webu).

Soubor **TEST_FLOW_AGENT_WEB.md** ani **CO_KAM_NAHRAT_A_UPRAVIT.md** na PythonAnywhere nahrávat nemusíte – slouží jen u vás v projektu.



Test nahrání – [dnešní datum]




