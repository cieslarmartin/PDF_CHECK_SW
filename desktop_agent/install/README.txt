Složka instalátoru DokuCheck PRO
================================

1. Build exe (ze složky desktop_agent):
   pyinstaller dokucheck.spec

2. Sestavení setup.exe (Inno Setup 6):
   Z této složky:  iscc installer_config.iss
   Nebo z desktop_agent:  iscc install\installer_config.iss

3. Výstup: DokuCheckPRO_Setup_1.2.0.exe v této složce (install\).

Viz desktop_agent\BUILD_INSTALL.md pro certifikaci a detaily.
