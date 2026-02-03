@echo off
REM =============================================================================
REM Auto-deploy: commit a push na GitHub (pro Windows / lokální vývoj)
REM Spusťte z kořene repozitáře.
REM =============================================================================

cd /d "%~dp0"

echo Pridavam zmeny...
git add .
git commit -m "Auto-deploy update"
if errorlevel 1 (
  echo Nic k commitovani nebo chyba. Ukoncuji.
  pause
  exit /b 1
)

echo Odesilam na GitHub...
git push origin main
if errorlevel 1 (
  echo Chyba pri pushi.
  pause
  exit /b 1
)

echo.
echo ==========================================
echo   Odeslano na GitHub (origin main) - OK
echo ==========================================
pause
