# DokuCheck – Workflow a kontext (pro člověka)

Tento soubor slouží jako reference. AI kontext je v `.cursor/rules/WORKFLOW.mdc`.

---

## 1. Pracovní postup

- Na konci úkolu: seznam změněných souborů.
- Otázka: „Chcete tyto změny nyní nahrát na GitHub? [Ano/Ne]“.
- Po Ano: `git add .` → `git commit -m "zpráva"` → `git push origin main` + potvrzení výsledku.

## 2. Technický kontext

- Server: PythonAnywhere, venv Python 3.10.
- DB: SQLite, tabulka `license_tiers`.
- Login: anonymní „Vyzkoušet zdarma“ (Machine-ID, demo_trial@dokucheck.app).
- UI Agent: 1000×700, fixní header/footer, Treeview 35px, Segoe UI 10, Auto-Expand, stats bar.

## 3. Marketingová identita

- Produkt: **DokuCheck** (Projektový Strážce).
- Cílová skupina: projektanti a architekti (Portál stavebníka).
- Jazyk: **vše v češtině** (aplikace + Admin Dashboard).

## 4. Efektivita

- Související změny v jednom „Editu“, šetřit kredity.
