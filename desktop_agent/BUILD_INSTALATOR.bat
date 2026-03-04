@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Build instalátoru DokuCheck
echo.
set "OUTPUT_DIR="
set /p "OUTPUT_DIR=Zadejte cestu pro kopii instalátoru (Enter = pouze install\): "
if defined OUTPUT_DIR set "DOKUCHECK_INSTALL_OUTPUT=%OUTPUT_DIR%"
echo.
echo Spouštím build...
echo.
python build_installer.py %*
if defined DOKUCHECK_INSTALL_OUTPUT set "DOKUCHECK_INSTALL_OUTPUT="
echo.
pause
