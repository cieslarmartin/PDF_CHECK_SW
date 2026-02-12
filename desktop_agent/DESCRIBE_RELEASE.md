# Šablona popisu release na GitHubu

Při vytváření nového release (Releases → Draft a new release) vyplňte:

- **Tag:** `v46` (nebo `v1.2.46` – sjednoťte s číslem v `version.py`: BUILD_VERSION)
- **Release title:** `DokuCheck PRO – Build 46` (nebo aktuální build)
- **Description:** zkopírujte a upravte níže.

---

## Popis release (zkopírujte do pole Description)

```markdown
## DokuCheck PRO – Build 46

Instalátor desktopové aplikace DokuCheck PRO pro kontrolu PDF dokumentů (PDF/A, metadata, poškození).

### Stažení
- **Soubor:** `DokuCheckPRO_Setup_46_YYYY-MM-DD.exe` (nahrajte z `desktop_agent/install/` po buildu)
- **Systém:** Windows 64 bit

### Co je v této verzi (Build 46)
- Kontrola PDF a složek (strom, drag & drop)
- Přihlášení licencí (e-mail + heslo) a zkušební režim
- Propojení s portálem DokuCheck (limity, účty)
- Zobrazení buildu v aplikaci (patička) pro snadnou identifikaci verze

### Instalace
1. Stáhněte `DokuCheckPRO_Setup_46_YYYY-MM-DD.exe`.
2. Spusťte a postupujte průvodcem (doporučeno instalovat do výchozí složky).
3. Po instalaci spusťte **DokuCheck PRO** z nabídky Start nebo z plochy.

### Verze
- **Build:** 46  
- Číslo buildu je vidět v aplikaci v levém panelu dole („Build 46“).

---
© 2025 Ing. Martin Cieślar · [DokuCheck](https://www.dokucheck.cz)
```

---

## Před každým release

1. **Zvýšit build** v `desktop_agent/version.py`: změňte `BUILD_VERSION = "46"` na nové číslo.
2. **Spustit build instalátoru:**  
   `cd desktop_agent` → `python build_installer.py`  
   Výstup: `desktop_agent/install/DokuCheckPRO_Setup_<verze>_<datum>.exe`
3. **Vytvořit release na GitHubu:** tag `v<verze>`, nahrajte tento .exe, popis podle šablony výše (nahraďte 46 a YYYY-MM-DD).
