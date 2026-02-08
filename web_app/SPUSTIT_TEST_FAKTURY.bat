@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   Test faktury - instalace a beh
echo ============================================
echo.

echo [1/3] Instalace zavisnosti (fpdf2, qrcode)...
python -m pip install fpdf2 qrcode
if errorlevel 1 (
    echo.
    echo Prikaz 'python -m pip' selhal, zkusim 'py -m pip'...
    py -m pip install fpdf2 qrcode
)
echo.

echo [2/3] Spousteni test_invoice.py...
python test_invoice.py
if errorlevel 1 (
    echo.
    echo Prikaz 'python' selhal, zkusim 'py'...
    py test_invoice.py
)
set EXITCODE=%ERRORLEVEL%
echo.

echo [3/3] Hotovo. Exit code: %EXITCODE%
echo.
echo Vystup vygenerovaneho PDF: test_faktura.pdf v aktualni slozce.
echo Tento log muzes zkopirovat a vlepit kam potrebujes.
echo.
pause
