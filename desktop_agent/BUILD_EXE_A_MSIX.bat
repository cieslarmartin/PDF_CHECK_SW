@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo  DokuCheck - vytvori EXE instalator + MSIX pro Store
echo  (stejny build z version.py, jeden PyInstaller)
echo ============================================================
echo.
echo  Vystupy:
echo    install\DokuCheckPRO_Setup_{BUILD}_{datum}.exe   - otestujte
echo    store\output\DokuCheck_{BUILD}.msix              - pak na Store
echo.
set "OUTPUT_DIR="
set /p "OUTPUT_DIR=Volitelna kopie EXE (Enter = jen install\): "
if defined OUTPUT_DIR set "DOKUCHECK_INSTALL_OUTPUT=%OUTPUT_DIR%"
echo.
echo Spoustim build...
echo.
python build_exe_and_msix.py %*
set "ERR=%ERRORLEVEL%"
if defined DOKUCHECK_INSTALL_OUTPUT set "DOKUCHECK_INSTALL_OUTPUT="
echo.
if not "%ERR%"=="0" (
    echo Build selhal (kod %ERR%).
) else (
    echo Hotovo. Nejdrive otestujte EXE, potom nahrajte MSIX.
)
pause
exit /b %ERR%
