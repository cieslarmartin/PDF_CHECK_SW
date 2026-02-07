# Přesný návod: jak získat Setup.exe (DokuCheck PRO instalátor)

Build skript `build_installer.py` vytvoří jeden soubor **DokuCheckPRO_Setup_{verze}_{datum}.exe** ve složce `desktop_agent/install/`. K tomu potřebuje nainstalované **Python** (včetně závislostí agenta), **PyInstaller** a **Inno Setup 6**.

---

## 1. Co musíte mít nainstalované

### Python 3.x
- Stáhněte z [python.org](https://www.python.org/downloads/) (doporučeno 3.10 nebo 3.11).
- Při instalaci zaškrtněte **„Add Python to PATH“**.

### Závislosti agenta
V terminálu přejděte do složky agenta a nainstalujte balíčky:

```text
cd c:\Claude\PDF_CHECK_SW\desktop_agent
pip install -r requirements.txt
```

### PyInstaller (nutné pro vytvoření exe)
```text
pip install pyinstaller
```

Ověření: `py -m PyInstaller --version` (nebo `python -m PyInstaller --version`) by mělo vypsat číslo verze.

### Inno Setup 6
- Stáhněte z [jrsoftware.org](https://jrsoftware.org/isdl.php) (Inno Setup 6).
- Nainstalujte do výchozí složky (32bit: `C:\Program Files (x86)\Inno Setup 6\`, 64bit: `C:\Program Files\Inno Setup 6\`).
- Skript `build_installer.py` obě cesty zkusí; **do PATH ho dávat nemusíte**.

---

## 2. Jediný příkaz pro sestavení instalátoru

Otevřete **PowerShell** nebo **Příkazový řádek** (cmd) a spusťte:

```text
cd c:\Claude\PDF_CHECK_SW\desktop_agent
python build_installer.py
```

(Případně `py build_installer.py`, pokud máte více verzí Pythonu.)

- Skript nejdřív zkontroluje PyInstaller a Inno Setup, pak spustí PyInstaller, pak Inno Setup, přejmenuje výstup a smaže složky `build/` a `dist/`.
- Pokud něco selže, v terminálu uvidíte chybovou hlášku a na konci „Stiskněte Enter pro ukončení…“.

---

## 3. Kde najdete výsledný Setup.exe

Po úspěšném běhu:

- **Složka:** `c:\Claude\PDF_CHECK_SW\desktop_agent\install\`
- **Soubor:** `DokuCheckPRO_Setup_46_2025-02-04.exe` (číslo verze z `ui.py` – BUILD_VERSION – a dnešní datum).

Tento soubor můžete distribuovat a uživatelé jím nainstalují DokuCheck PRO.

---

## 4. Časté problémy

| Problém | Řešení |
|--------|--------|
| „PyInstaller není nainstalovaný“ | `pip install pyinstaller` |
| „Inno Setup 6 (ISCC) nenalezen“ | Nainstalujte Inno Setup 6 do výchozí složky; skript hledá `C:\Program Files (x86)\Inno Setup 6\ISCC.exe` a `C:\Program Files\Inno Setup 6\ISCC.exe`. |
| „Po PyInstalleru chybí … DokuCheckPRO.exe“ | Podívejte se na výstup PyInstalleru – chybějící modul (např. PIL, customtkinter) nainstalujte: `pip install -r requirements.txt`. |
| Skript „nic neudělá“ / okno zmizí | Spouštějte z terminálu (cmd/PowerShell), ne dvojklikem na .py. Uvidíte případné chyby. |
| Verze v názvu exe | Verze se bere z `ui.py` z řádku `BUILD_VERSION = "46"`. Pro jinou verzi (např. 1.2.0) tam hodnotu změňte. |

---

## 5. Shrnutí kroků (zkráceně)

1. Nainstalovat Python (s PATH).
2. `cd c:\Claude\PDF_CHECK_SW\desktop_agent`
3. `pip install -r requirements.txt`
4. `pip install pyinstaller`
5. Nainstalovat Inno Setup 6 (výchozí cesta).
6. `python build_installer.py`
7. Setup.exe je v `desktop_agent\install\`.
