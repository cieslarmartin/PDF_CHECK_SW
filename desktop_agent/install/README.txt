Složka instalátoru DokuCheck PRO
================================

Automatický build (doporučeno):
  Ze složky desktop_agent spusťte:
    python build_installer.py
  Skript detekuje verzi z ui.py (BUILD_VERSION), spustí PyInstaller a Inno Setup,
  přejmenuje výstup na DokuCheckPRO_Setup_{verze}_{datum}.exe a smaže build/ a dist/.

Ruční build:
1. Ze složky desktop_agent: pyinstaller dokucheck.spec
2. Z této složky: iscc installer_config.iss  (nebo z desktop_agent: iscc install\installer_config.iss)
3. Výstup: DokuCheckPRO_Setup_{verze}.exe v install\

Viz desktop_agent\BUILD_INSTALL.md pro certifikaci a detaily.
