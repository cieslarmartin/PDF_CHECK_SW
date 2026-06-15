# DokuCheck – MSIX balíček pro Microsoft Store

Oddělená složka `desktop_agent/store/` – **nezasahuje** do `.exe` instalátoru (`build_installer.py` / `install/`).

## Identita produktu (Partner Center)

| Pole | Hodnota |
|------|---------|
| Identity Name | `MartinCielar.DokuCheck` |
| Publisher | `CN=4578E17D-2158-43EA-A0A4-8C07416BEC45` |
| Store ID | `9N88TSSMV07Z` |
| Odkaz do Storu | https://apps.microsoft.com/detail/9N88TSSMV07Z |

Manifest: `store/msix/AppxManifest.xml`

---

## Sestavení MSIX

```batch
cd c:\CURSOR_SOUBORY\Claude\PDF_CHECK_SW\desktop_agent
pip install -r requirements.txt pyinstaller pillow
python store/build_msix.py
```

Pouze zabalení (už existuje `dist/DokuCheckPRO/`):

```batch
python store/build_msix.py --skip-build
```

**Výstup:** `desktop_agent/store/output/DokuCheck_{BUILD}.msix`

Regenerace ikon: `python store/msix/generate_assets.py`

---

## Lokální test

```powershell
Add-AppxPackage -Path "c:\CURSOR_SOUBORY\Claude\PDF_CHECK_SW\desktop_agent\store\output\DokuCheck_53.msix"
```

Odinstalace: Nastavení → Aplikace → DokuCheck → Odinstalovat.

---

## Partner Center

1. **Start submission** → Packages → nahrajte `.msix` ze `store/output/`
2. Store listing (čeština), screenshoty, privacy URL (`https://www.dokucheck.cz/gdpr`)
3. Properties, Age ratings, Pricing **Free**
4. Submit for certification

---

## Po schválení Microsoftu

Teprve pak upravit web (`/download`) a nasadit na PythonAnywhere. Do té doby zůstává distribuce přes `.exe`.
