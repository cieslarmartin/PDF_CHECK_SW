# CURSOR PROMPT — DokuCheck.cz Landing Page Redesign
## Instrukce: POUZE VIZUÁLNÍ ZMĚNY, nulové změny funkcionality

---

## KONTEXT A PRAVIDLA

Tento prompt mění **výhradně HTML/CSS strukturu a texty** stávající landing page DokuCheck.cz.

**NESMÍŠ:**
- Měnit žádné URL adresy, href, action atributy formulářů
- Měnit žádný backend kód, Python/Flask/FastAPI routy
- Měnit žádnou business logiku, validační kód, autentizaci
- Přidávat nové JS funkce (pouze CSS transitions)
- Měnit strukturu databáze nebo API endpointy
- Měnit soubory mimo složku templates/ a static/css/

**SMÍŠ:**
- Přeskupit sekce stránky (změnit pořadí HTML bloků)
- Upravit texty (nadpisy, popisy, CTA texty)
- Přidat/upravit CSS třídy a styly
- Přidat HTML elementy čistě dekorativní povahy (ikonky, badge, oddělovače)
- Sloučit nebo rozdělit stávající sekce vizuálně

---

## BAREVNÁ PALETA (zachovat beze změny)

```css
--color-primary: #1e5a8a;        /* modrá — hlavní brand barva */
--color-primary-hover: #2d7ab8;  /* světlejší modrá na hover */
--color-success: #16A34A;        /* zelená — schválení, checkmarky */
--color-success-light: #22c55e;  /* světlá zelená */
--color-bg: #ffffff;             /* bílé pozadí */
--color-bg-subtle: #f8f9fc;      /* jemně šedé pozadí sekcí */
--color-text: #0f172a;           /* hlavní text */
--color-text-muted: #64748b;     /* sekundární text */
--color-border: #e2e8f0;         /* okraje karet */
```

Písmo zůstane stávající (nebo 'Plus Jakarta Sans' pokud není nastaveno).

---

## ZMĚNA 1: SMAZAT TYTO BLOKY ÚPLNĚ

Najdi a **odstraň** z HTML následující elementy:

```
# 1. Upozornění o pilotním provozu v hero sekci:
<p>Aplikace je v pilotním provozu...</p>
<p>Hláška systému SmartScreen je očekávaná...</p>

# 2. Poznámku "Info: Aplikace je v pilotním provozu" v sekci stažení:
<div class="...">Info: Aplikace je v pilotním provozu...</div>

# 3. Tlačítko "Můj účet" z hero sekce (nechat pouze v navbaru):
<a href="/portal">Můj účet</a>   ← pouze to v hero, ne v navbaru

# 4. Badge/text "w26.02.XXX · Portál stavebníka" z hero (pokud je viditelný uživateli)
```

---

## ZMĚNA 2: NOVÝ HERO BLOK

Nahraď stávající hero sekci tímto obsahem (zachovej stávající obalovací div a jeho CSS třídy, vyměň pouze vnitřní HTML):

```html
<!-- HERO SEKCE — nový obsah -->

<!-- Announcement bar (horní proužek) — pouze tuto větu -->
<div class="announcement-bar">
  🔥 Aktualizováno pro nejnovější požadavky Portálu stavebníka 2026 — PDF/A-3, PostSignum, I.CA, eIdentity
</div>

<!-- Hero hlavní obsah -->
<div class="hero-content">

  <!-- Levá část: text -->
  <div class="hero-text">

    <!-- Badge nad nadpisem -->
    <div class="hero-badge">
      <span class="badge-dot"></span>
      Pro autorizované inženýry ČKAIT a projektové kanceláře
    </div>

    <!-- Hlavní nadpis — TOTO JE NEJDŮLEŽITĚJŠÍ ZMĚNA -->
    <h1 class="hero-heading">
      Projděte Portál stavebníka<br>
      <span class="hero-heading-accent">napoprvé. Bez vracení.</span>
    </h1>

    <!-- Podnadpis -->
    <p class="hero-subheading">
      DokuCheck automaticky ověří PDF/A-3, elektronické podpisy a časová razítka
      ještě před odesláním dokumentace. Kontrola za 2–5 minut.
    </p>

    <!-- Cena viditelná hned v hero -->
    <div class="hero-pricing-teaser">
      <span class="pricing-from">Od</span>
      <span class="pricing-amount">91 Kč</span>
      <span class="pricing-period">/měsíc</span>
      <span class="pricing-annual">(1 090 Kč/rok · roční licence)</span>
    </div>

    <!-- CTA tlačítka — MAX 2, jasná hierarchie -->
    <div class="hero-cta-group">
      <a href="/checkout?tarif=basic" class="btn-primary btn-large">
        Zakoupit licenci →
      </a>
      <a href="/app" class="btn-secondary btn-large">
        Vyzkoušet online zdarma
      </a>
    </div>

    <!-- Trust signály pod tlačítky -->
    <div class="hero-trust-signals">
      <span class="trust-item">✓ Žádná instalace pro online verzi</span>
      <span class="trust-item">✓ Data zůstávají u vás (Agent režim)</span>
      <span class="trust-item">✓ PostSignum · I.CA · eIdentity</span>
    </div>

  </div>

  <!-- Pravá část: vizuál — mockup výsledku kontroly -->
  <div class="hero-visual">
    <div class="mockup-window">
      <div class="mockup-titlebar">
        <span class="mockup-dot red"></span>
        <span class="mockup-dot yellow"></span>
        <span class="mockup-dot green"></span>
        <span class="mockup-filename">projekt_bytovy_dum.pdf</span>
      </div>
      <div class="mockup-content">
        <div class="mockup-row pass">
          <span class="mockup-icon">✓</span>
          <span class="mockup-label">Formát PDF/A-3</span>
          <span class="mockup-status pass">OK</span>
        </div>
        <div class="mockup-row pass">
          <span class="mockup-icon">✓</span>
          <span class="mockup-label">Elektronický podpis (PostSignum)</span>
          <span class="mockup-status pass">Platný</span>
        </div>
        <div class="mockup-row pass">
          <span class="mockup-icon">✓</span>
          <span class="mockup-label">Časové razítko TSA</span>
          <span class="mockup-status pass">Ověřeno</span>
        </div>
        <div class="mockup-row pass">
          <span class="mockup-icon">✓</span>
          <span class="mockup-label">Autorizační razítko (ČKAIT)</span>
          <span class="mockup-status pass">Nalezeno</span>
        </div>
        <div class="mockup-row warn">
          <span class="mockup-icon">!</span>
          <span class="mockup-label">Klíčová slova v metadatech</span>
          <span class="mockup-status warn">Chybí</span>
        </div>
        <div class="mockup-progress-section">
          <div class="mockup-progress-label">Celkový stav: 4/5 kontrol prošlo</div>
          <div class="mockup-progress-bar">
            <div class="mockup-progress-fill" style="width: 80%;"></div>
          </div>
        </div>
      </div>
    </div>
  </div>

</div>
```

**CSS pro hero — přidej do main.css nebo inline:**

```css
/* Hero badge */
.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: #ecfdf5;
  color: #16A34A;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 20px;
  border: 1px solid #bbf7d0;
}
.badge-dot {
  width: 7px;
  height: 7px;
  background: #16A34A;
  border-radius: 50%;
  display: inline-block;
}

/* Hero nadpis */
.hero-heading {
  font-size: clamp(32px, 4.5vw, 52px);
  font-weight: 800;
  line-height: 1.1;
  letter-spacing: -1.5px;
  margin-bottom: 18px;
  color: #0f172a;
}
.hero-heading-accent {
  color: #1e5a8a;
}

/* Pricing teaser v hero */
.hero-pricing-teaser {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 28px;
  flex-wrap: wrap;
}
.pricing-from {
  font-size: 14px;
  color: #64748b;
}
.pricing-amount {
  font-size: 28px;
  font-weight: 800;
  color: #1e5a8a;
}
.pricing-period {
  font-size: 14px;
  color: #64748b;
}
.pricing-annual {
  font-size: 12px;
  color: #94a3b8;
  margin-left: 4px;
}

/* CTA skupina */
.hero-cta-group {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.btn-large {
  padding: 14px 28px;
  font-size: 16px;
  font-weight: 700;
  border-radius: 12px;
  text-decoration: none;
  transition: all 0.25s ease;
  display: inline-block;
}
.btn-primary {
  background: #1e5a8a;
  color: #ffffff;
  border: none;
}
.btn-primary:hover {
  background: #2d7ab8;
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(30, 90, 138, 0.3);
}
.btn-secondary {
  background: transparent;
  color: #1e5a8a;
  border: 2px solid #e2e8f0;
}
.btn-secondary:hover {
  border-color: #1e5a8a;
  background: #f0f7ff;
}

/* Trust signály */
.hero-trust-signals {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.trust-item {
  font-size: 13px;
  color: #64748b;
}

/* Mockup okno */
.mockup-window {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.08);
}
.mockup-titlebar {
  background: #f8f9fc;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 6px;
  border-bottom: 1px solid #e2e8f0;
}
.mockup-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.mockup-dot.red    { background: #ef4444; }
.mockup-dot.yellow { background: #f59e0b; }
.mockup-dot.green  { background: #22c55e; }
.mockup-filename {
  font-size: 12px;
  color: #94a3b8;
  margin-left: 8px;
}
.mockup-content {
  padding: 20px;
}
.mockup-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 0;
  border-bottom: 1px solid #f1f5f9;
  font-size: 14px;
}
.mockup-row:last-child { border: none; }
.mockup-icon {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
.mockup-row.pass .mockup-icon { background: #dcfce7; color: #16A34A; }
.mockup-row.warn .mockup-icon { background: #fef3c7; color: #d97706; }
.mockup-row.fail .mockup-icon { background: #fee2e2; color: #ef4444; }
.mockup-label { flex: 1; color: #374151; }
.mockup-status {
  font-size: 12px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
}
.mockup-status.pass { background: #dcfce7; color: #16A34A; }
.mockup-status.warn { background: #fef3c7; color: #d97706; }
.mockup-status.fail { background: #fee2e2; color: #ef4444; }
.mockup-progress-section {
  padding-top: 14px;
}
.mockup-progress-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}
.mockup-progress-bar {
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
}
.mockup-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #1e5a8a, #22c55e);
  border-radius: 4px;
}

/* Dark mode podpora */
@media (prefers-color-scheme: dark) {
  .hero-heading { color: #ffffff; }
  .mockup-window { background: #151820; border-color: #1e2536; }
  .mockup-titlebar { background: #0c0f1a; border-color: #1e2536; }
  .mockup-label { color: #c8d0e0; }
  .mockup-row { border-color: #1e2536; }
  .hero-badge { background: rgba(34,197,94,0.1); border-color: rgba(34,197,94,0.2); }
}
```

---

## ZMĚNA 3: PŘESKUPENÍ SEKCÍ

Přeřaď sekce na stránce do tohoto pořadí (zachovej kompletní HTML každé sekce, jen změň jejich pozici):

```
1. [NOVÝ] Announcement bar (proužek)
2. [NOVÝ] Hero (dle výše)
3. [ZACHOVAT] Jak to funguje (#jak) — 3 kroky
4. [ZACHOVAT] Jistota před expedicí — srovnávací tabulka (#problem-reseni)
5. [ZACHOVAT] Pro koho (#pro-koho)
6. [ZACHOVAT] Dva režimy: Z Agenta vs Cloud (#dva-rezimy)
7. [ZACHOVAT] Ceník (#cenik) — viz Změna 4
8. [ZACHOVAT + SLOUČIT] Stažení aplikace + Co je nového (#download + #news)
9. [ZACHOVAT, snížit vizuální důraz] Připravujeme (#pripravujeme)
10. [ZACHOVAT] FAQ (#faq)
11. [ZACHOVAT] Kontakt (#kontakt)
12. [ZACHOVAT] Footer
```

**Sekce "Co je nového" — přesuň** z pozice 2 (kde je nyní, hned za hero) dolů na pozici 8, sloučenou se sekcí Stažení.

---

## ZMĚNA 4: ÚPRAVA CENÍKU

V sekci Ceník uprav karty takto (zachovej stávající `href` na `/checkout?tarif=basic` a `/checkout?tarif=standard`):

```html
<!-- Přidej nad cenu měsíční přepočet -->
<div class="price-monthly-note">
  jen <strong>91 Kč/měsíc</strong> při ročním předplatném
</div>

<!-- Původní cena zůstane, přidej pod ni tuto větu: -->
<p class="price-annual">1 090 Kč/rok · placeno ročně</p>
```

Pro PRO plán:
```html
<div class="price-monthly-note">
  jen <strong>133 Kč/měsíc</strong> při ročním předplatném
</div>
<p class="price-annual">1 590 Kč/rok · placeno ročně</p>
```

CSS pro ceník doplněk:
```css
.price-monthly-note {
  font-size: 15px;
  color: #16A34A;
  margin-bottom: 4px;
}
.price-monthly-note strong {
  font-size: 22px;
  font-weight: 800;
}
.price-annual {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 0;
}
```

**Odstraň z ceníku** větu:
```
"🔒 Z Agenta: soubory u vás, na server jdou jen metadata (výsledky kontroly)."
```
Tuto informaci přesuň do sekce "Dva režimy", kde logicky patří.

---

## ZMĚNA 5: NAVBAR — ZJEDNODUŠENÍ

Navbar má 10 položek. Zkrátit na max 6 viditelných + dropdown nebo skrytí:

```html
<!-- Zachovat viditelné: -->
<a href="#jak">Jak to funguje</a>
<a href="#cenik">Ceník</a>
<a href="#faq">FAQ</a>
<a href="/download/agent">Ke stažení</a>

<!-- Přesunout do "Více" dropdown nebo Footer: -->
<!-- Srovnání, Pro koho, Režimy, Připravujeme, Novinky -->

<!-- Zachovat vždy viditelné vpravo: -->
<a href="/portal" class="btn-nav-secondary">Přihlásit</a>
<a href="/checkout?tarif=basic" class="btn-nav-primary">Koupit licenci</a>
```

CSS pro navbar tlačítka:
```css
.btn-nav-primary {
  background: #1e5a8a;
  color: #fff;
  padding: 8px 18px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 14px;
  text-decoration: none;
  transition: background 0.2s;
}
.btn-nav-primary:hover { background: #2d7ab8; }
.btn-nav-secondary {
  color: #64748b;
  padding: 8px 14px;
  font-weight: 500;
  font-size: 14px;
  text-decoration: none;
}
.btn-nav-secondary:hover { color: #0f172a; }
```

---

## ZMĚNA 6: PŘIDAT TRUST SEKCI (nová, hned za hero)

Za hero sekci přidej krátký pás důvěryhodnosti:

```html
<div class="trust-bar">
  <div class="trust-bar-inner">
    <div class="trust-bar-item">
      <span class="trust-bar-number">PDF/A-3</span>
      <span class="trust-bar-label">ISO 19005-3 standard</span>
    </div>
    <div class="trust-bar-divider"></div>
    <div class="trust-bar-item">
      <span class="trust-bar-number">PostSignum</span>
      <span class="trust-bar-label">I.CA · eIdentity</span>
    </div>
    <div class="trust-bar-divider"></div>
    <div class="trust-bar-item">
      <span class="trust-bar-number">MMR metodika</span>
      <span class="trust-bar-label">Digitální stavební řízení</span>
    </div>
    <div class="trust-bar-divider"></div>
    <div class="trust-bar-item">
      <span class="trust-bar-number">ČKAIT</span>
      <span class="trust-bar-label">Autorizovaní inženýři</span>
    </div>
  </div>
</div>
```

CSS:
```css
.trust-bar {
  background: #f8f9fc;
  border-top: 1px solid #e2e8f0;
  border-bottom: 1px solid #e2e8f0;
  padding: 20px 5%;
}
.trust-bar-inner {
  max-width: 900px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
}
.trust-bar-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 2px;
}
.trust-bar-number {
  font-size: 15px;
  font-weight: 700;
  color: #1e5a8a;
}
.trust-bar-label {
  font-size: 12px;
  color: #94a3b8;
}
.trust-bar-divider {
  width: 1px;
  height: 36px;
  background: #e2e8f0;
}
@media (max-width: 600px) {
  .trust-bar-divider { display: none; }
  .trust-bar-inner { justify-content: center; }
}
```

---

## SHRNUTÍ ZMĚN PRO CURSOR

| # | Typ změny | Soubor | Popis |
|---|-----------|--------|-------|
| 1 | Smazat | template/index.html | Odstranit disclaimery o pilotním provozu a SmartScreen |
| 2 | Nahradit | template/index.html | Celý hero blok novým (viz Změna 2) |
| 3 | Přesunout | template/index.html | Přeřadit sekce do nového pořadí (viz Změna 3) |
| 4 | Upravit text | template/index.html | Ceník — přidat měsíční přepočet (viz Změna 4) |
| 5 | Zkrátit | template/index.html | Navbar z 10 na 6 položek (viz Změna 5) |
| 6 | Přidat | template/index.html | Trust bar pod hero (viz Změna 6) |
| 7 | Přidat | static/css/main.css | Všechny nové CSS třídy dle tohoto promptu |

**ŽÁDNÁ z těchto změn nemění URL, routy, Flask views, databázi ani business logiku.**

---

## TESTOVACÍ CHECKLIST PO IMPLEMENTACI

- [ ] Hero nadpis: první věta odpovídá výsledku, ne popisu nástroje
- [ ] Cena je viditelná bez scrollování (91 Kč/měsíc v hero)
- [ ] Pouze 2 CTA tlačítka v hero (Zakoupit + Vyzkoušet)
- [ ] Žádný disclaimer o pilotním provozu nebo SmartScreen na stránce
- [ ] Navbar má max 6 položek + 2 tlačítka vpravo
- [ ] Sekce „Co je nového" je až za ceníkem / před FAQ
- [ ] Tlačítko „Zakoupit Basic" vede na `/checkout?tarif=basic` ✓
- [ ] Tlačítko „Zakoupit Pro" vede na `/checkout?tarif=standard` ✓
- [ ] Tlačítko „Vyzkoušet" vede na `/app` ✓
- [ ] Stránka je responzivní na mobilech (hero se skládá pod sebe)
