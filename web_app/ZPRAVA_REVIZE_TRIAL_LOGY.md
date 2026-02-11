# Zpráva o revizi – Trial, Logy, Dashboard

## 1. Databáze

### Tabulky (vše existují v `database.py` init_database):

| Tabulka | Účel |
|---------|------|
| `trial_usage` | Agent Trial – limit podle machine_id |
| `web_trial_ip_usage` | Web Trial – limit 3 batche/24h na IP |
| `activity_log` | Sjednocený log (Web Trial + Agent + Registrovaný) |

### Nově: Migrační skript
- **`db_migration_trial_activity.py`** – spusť na PythonAnywhere po nasazení, pokud tabulky chybí:  
  `cd ~/web_app && python db_migration_trial_activity.py`

### Logování po dávkách
- **activity_log**: 1 záznam = 1 dávka (volá se `insert_activity_log` jednou při `/analyze-batch` nebo `/api/batch/upload`)
- **user_logs**: stále 1 záznam = 1 batch (insert_user_log při batch/upload)

---

## 2. Logika IP limitu (pdf_check_web_main.py)

- **Route:** `/analyze-batch` (Online Check) a `/analyze` (legacy jedno soubor)
- **Kontrola:** `db.check_web_trial_limit(ip)` před zpracováním
- **Limit:** max 3 batche za 24 h na IP (tabulka `web_trial_ip_usage`)
- **Záznam:** `db.record_web_trial_usage(ip)` + `db.insert_activity_log(..., source_type='web_trial')`

---

## 3. Reorganizace dashboardu

### Sidebar (admin_base.html)
- **Předtím:** jeden odkaz „Nástěnka“
- **Nyní:** dva odkazy – „Uživatelé“ (#users) a „Statistiky a Logy“ (#stats-logs)

### Obsah admin_dashboard.html
- **1. Uživatelé** – tabulka licencí
- **2. Statistiky a Logy** – KPI (kontrol dnes, Trial batche, aktivní licence) + sjednocený activity_log s tlačítkem „Resetovat IP“

### Stránka Logy (admin_logs.html)
- **Nový tab „Aktivita (sjednocený)“** – výchozí, zobrazuje activity_log (Web Trial, Agent, Registrovaný)
- Tlačítko „Resetovat IP“ u záznamů Web Trial

---

## 4. Logování Agenta (api_endpoint.py)

- Endpoint: `/api/batch/upload`
- Po úspěšném uploadu: `db.insert_activity_log(ip_address=..., source_type='agent', file_count=saved_count, api_key=api_key)`
- Záznamy se zobrazují ve stejném logu (activity_log) jako Web Trial

---

## Proč se změny mohly neprojevit

1. **Kód nebyl nasazen** – chyběl `git push` nebo pull na PythonAnywhere.
2. **Tabulky neexistovaly** – stará databáze bez nových tabulek. Řešení: spustit `db_migration_trial_activity.py`.
3. **Cache prohlížeče** – hard refresh (Ctrl+F5) nebo vymazání cache.
4. **Cesta ke šablonám** – projekt používá `templates/admin_*.html`, ne `templates/admin/`.

---

## Změněné soubory (revize)

| Soubor | Změna |
|--------|-------|
| `db_migration_trial_activity.py` | Nový – migrace trial/activity tabulek |
| `admin_routes.py` | Logy: přidán category='activity', výchozí tab Aktivita |
| `templates/admin_logs.html` | Tab Aktivita, tabulka activity_log, Reset IP |
| `templates/admin_base.html` | Sidebar: Uživatelé + Statistiky a Logy |
| `version.py` | Build 47, w26.02.003 |
