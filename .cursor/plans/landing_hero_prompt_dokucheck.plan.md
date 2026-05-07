---
name: Landing redesign dle dokucheck-cursor-prompt
overview: Implementovat vizuální a obsahové změny z [dokucheck-cursor-prompt.md](../../dokucheck-cursor-prompt.md) na produkční šabloně [web_app/templates/landing_v3.html](../../web_app/templates/landing_v3.html) s CSS v [web_app/static/css/](../../web_app/static/css/), náhled přes nový route před nasazením na `/`, bump [web_app/version.py](../../web_app/version.py).
todos:
  - id: hero-announce-trust
    content: Hero + announcement text + trust bar (Změna 2, 6); odstranit pilot z hero, Můj účet z hero
    status: pending
  - id: reorder-sections
    content: Přesun #news pod sloučení se stažením (Změna 3)
    status: pending
  - id: pricing-navbar
    content: Ceník doplněk + přesun 🔒 textu do #dva-rezimy; navbar zkrátit + CTA (Změna 4–5)
    status: pending
  - id: css-assets
    content: Nové třídy do static CSS (ne main.css pokud neexistuje – založit nebo landing.css)
    status: pending
  - id: preview-route
    content: /landing-draft stejné settings jako index; po schválení sloučit do landing_v3
    status: pending
  - id: version-bump
    content: web_app/version.py WEB_BUILD + WEB_VERSION
    status: pending
isProject: true
---

# Landing + hero podle [dokucheck-cursor-prompt.md](../../dokucheck-cursor-prompt.md)

## Zdroj pravdy

- Prompt v kořeni projektu: [dokucheck-cursor-prompt.md](../../dokucheck-cursor-prompt.md)
- Produkční route `/` → [web_app/pdf_check_web_main.py](../../web_app/pdf_check_web_main.py) → `landing_v3.html`
- Prompt cílí na `template/index.html` + `main.css` — **v tomto repo** nahradit za `web_app/templates/landing_v3.html` a existující / nový soubor pod `web_app/static/css/`

## Upřesnění oproti textu promptu (konzistence s repo)

1. **Announcement bar**: V [landing_v3.html](../../web_app/templates/landing_v3.html) už existuje horní `.announce-bar` **mimo** hero. Prompt vkládá `announcement-bar` do náhrady hero — **implementovat jako jednu** horní lištu (aktualizovat text dle promptu), **bez duplicity**.
2. **Dark mode**: Stávající stránka používá `[data-theme="dark"]` a `toggleTheme()`, ne jen `prefers-color-scheme`. CSS z promptu převést / doplnit selektory pro `data-theme` tam, kde to ovlivní nové bloky.
3. **Jinja / Admin**: Zachovat `landing_hero_*`, CTA a pilot přepínače tam, kde má smysl — nebo staticky dle promptu a sjednotit `h1` s `landing_hero_title` (viz dřívější poznámka v plánu). Po odstranění pilot textů z UI stále může `{% if show_pilot_notice %}` zůstat v šabloně prázdný — cíl promptu je **nic nezobrazovat**.
4. **Splash**: Řádek s `{{ web_version }} · Portál stavebníka` je ve **splash** overlay, ne v hero — rozhodnutí při exekuci: odstranit / zkrátit dle checklistu („žádný w26…”).

## Rozpor v promptu (k vyjasnění s vámi před mergem na `/`)

- Úvod promptu říká „nesmíš měnit href“; návrh hero a navbar **explicitně zavádí** `/checkout?tarif=basic`, `/app`, `/portal`. V `landing_v3` už **checkout** na ceníku je — hero jen **mění** primární CTA z aktuálního stavu na „Zakoupit licenci“.
- Navbar prompt mění odkaz „Můj účet“ na „Přihlásit“ (`/portal` — stejné URL, jiný text: OK).

## Mapování změn → soubory

| Změna | Akce |
|--------|------|
| 1 Odstranit pilot / SmartScreen / Info stažení | Odstranit bloky `show_pilot_notice` v hero a u stažení; ověřit další výskyty textu globálně v šabloně |
| 1 Hero: odstranit Můj účet | Odstranit řádek 165 obdobný; nechat mobil/desktop nav odkazy na `/portal` |
| 2 Nový hero | Nahradit sekci `# ============ HERO ============` vnitřkem mockupem z promptu; layout 2 sloupce jako nyní (Tailwind + nové třídy) |
| 3 Pořadí sekcí | Přesunout blok `#news` až za `#cenik` a sloučit vizuálně se sekci stažení (`#download`) — struktura HTML podle promptu |
| 4 Ceník | Přidat `price-monthly-note` / `price-annual`; odstranit 🔒 odstavce z karet Basic/Pro; stejný text přidat do `#dva-rezimy` (sloupec Agent) |
| 5 Navbar | Max 6 odkazů + „Více“ (details/summary nebo rozbalovací) pro zbytek; vpravo Přihlásit + Koupit; mobilní menu sladit |
| 6 Trust bar | Nová sekce hned pod hero (před `#jak`) |
| CSS | Přesunout bloky z promptu do např. `web_app/static/css/landing-hero-prompt.css` + `<link>` v `landing_v3.html` (prompt dovoluje static/css) |

## Postup implementace

1. **Náhled**: Přidat route např. `GET /landing-draft` s `render_template('landing_v3_draft.html', **settings)` — kopie `landing_v3` + změny, stejný kontext jako `index()`.
2. **Kontrola**: Checklist řádky 593–605 v promptu.
3. **Produkce**: Přenést obsah draftu do `landing_v3.html`, smazat draft nebo nechat pro budoucí A/B.
4. **Verze**: [web_app/version.py](../../web_app/version.py)

## Nesahat (leží mimo prompt)

- Python routy, DB, JS logika kromě CSS transitions (dropdown pro „Více“ může být čisté HTML `<details>` bez nového JS).

## Po dokončení (workflow)

- Vypsat změněné soubory; zeptat se na GitHub push dle pravidel projektu.
