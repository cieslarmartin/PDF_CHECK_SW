@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo PDF DokuCheck Agent - spousteni...
echo.

REM Zkontroluj Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Chyba: Neni nainstalovan Python nebo neni v PATH.
    echo Nainstalujte Python z https://www.python.org/ a zaškrtněte "Add Python to PATH".
    pause
    exit /b 1
)

REM Volitelne: instalace zavislosti (odkomentujte pokud potrebujete)
REM pip install -r requirements.txt

python pdf_check_agent_main.py
if errorlevel 1 (
    echo.
    echo Agent skoncil s chybou. Zkuste: pip install -r requirements.txt
    pause
)
