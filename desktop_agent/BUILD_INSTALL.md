# DokuCheck PRO – Build a instalátor (Windows)

## Požadavky

- Python 3.10+ s balíčky: `pyinstaller`, `customtkinter`, `requests`, `PyYAML`, `tkinterdnd2`
- Inno Setup 6 (https://jrsoftware.org/isinfo.php)
- (Volitelně) Ikona `app_icon.ico` nebo `logo/logo.ico` v této složce

---

## 1. PyInstaller build (onedir, bez konzole)

V terminálu ze složky **desktop_agent**:

```batch
cd c:\Claude\PDF_CHECK_SW\desktop_agent
pyinstaller dokucheck.spec
```

Výstup: složka **`dist\DokuCheckPRO`** s souborem `DokuCheckPRO.exe` a závislostmi.

---

## 2. Inno Setup – vytvoření setup.exe

Po úspěšném PyInstaller buildu:

```batch
cd c:\Claude\PDF_CHECK_SW\desktop_agent
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer_config.iss
```

Nebo z GUI Inno Setup: Otevřít `installer_config.iss` → Build → Compile.

Výstup: **`desktop_agent\Output\DokuCheckPRO_Setup_1.2.0.exe`**

Instalátor:
- instaluje do `C:\Program Files\DokuCheckPRO` (nebo {autopf}\DokuCheckPRO)
- vytvoří zástupce v nabídce Start a volitelně na ploše
- přidá záznam do „Přidat nebo odebrat programy“ včetně odinstalování (Uninstaller)

---

## 3. Digitální certifikace (Microsoft Authenticode)

### Soubory k předání certifikační autoritě

1. **`Output\DokuCheckPRO_Setup_1.2.0.exe`** (nebo aktuální název) – hlavní soubor k podpisu  
   Po obdržení certifikátu (např. .pfx) doplňte do `installer_config.iss` v sekci `[Setup]`:

   ```ini
   SignTool=signtool sign /tr http://timestamp.digicert.com /td sha256 /fd sha256 /f "C:\cesta\k\cert.pfx" /p "heslo" $f
   ```

   Pak znovu spusťte Inno Setup – vygenerovaný setup.exe bude podepsaný.

2. (Podle požadavků CA může být potřeba i **podepsat samotné `DokuCheckPRO.exe`** v `dist\DokuCheckPRO\` před sestavením instalátoru. V tom případě přidejte do Inno Setup sekci `[Code]` nebo použijte předběžný krok: `signtool sign ... dist\DokuCheckPRO\DokuCheckPRO.exe`.)

### Typický postup u CA

- Objednání Code Signing certifikátu (OV nebo EV).
- Po vydání: stažení .pfx (nebo instalace do úložiště a export).
- Spuštění `signtool` na `DokuCheckPRO_Setup_xxx.exe` (nebo dle pokynů CA).
- Kontrola podpisu: pravý klik na setup.exe → Vlastnosti → Digitální podpisy.

---

## 4. Verze a údržba

- **Verze instalátoru:** upravte `MyAppVersion` v `installer_config.iss` (např. `1.2.0`).
- **Ikona:** pro exe i instalátor přidejte `app_icon.ico` do složky `desktop_agent` nebo `logo/logo.ico` (doporučeno 256×256 px, více rozlišení v .ico).
- **Config po instalaci:** uživatel má config a logy v **`%APPDATA%\PDF DokuCheck Agent`** (ne v Program Files), aby aplikace nepadala kvůli právům.
