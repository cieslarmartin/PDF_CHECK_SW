@echo off
chcp 65001 >nul
REM ============================================================
REM  Spuštění webu z disku (lokální test) – PDF_CHECK_SW
REM  Po spuštění otevři v prohlížeči: http://127.0.0.1:5000/
REM  Build se zobrazí v patičce landingu a v Admin dashboardu.
REM ============================================================

cd /d "%~dp0"

echo.
echo  Spouštím DokuCheck Web z disku...
echo  Po startu otevři: http://127.0.0.1:5000/
echo  Admin: http://127.0.0.1:5000/login
echo.

python pdf_check_web_main.py

if errorlevel 1 (
    echo.
    echo  Chyba pri spusteni. Zkontroluj, ze mas Python a zavislosti (pip install -r requirements.txt).
    pause
)
