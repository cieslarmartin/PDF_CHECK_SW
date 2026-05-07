@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

echo ==========================================
echo      ODESILANI ZMEN NA GITHUB (PUSH) - V2
echo ==========================================
echo.

cd /d "%~dp0"

REM --- Nastaveni identity jen pro tento repozitar (bez --global) ---
REM Pokud chcete zmenit hodnoty, upravte tyto 2 radky:
git config user.name "cieslarmartin" >nul 2>&1
git config user.email "cieslarm@seznam.cz" >nul 2>&1

echo Kontrola nastaveni autora:
for /f "delims=" %%A in ('git config user.name 2^>nul') do set "GIT_NAME=%%A"
for /f "delims=" %%A in ('git config user.email 2^>nul') do set "GIT_EMAIL=%%A"
echo   user.name  = !GIT_NAME!
echo   user.email = !GIT_EMAIL!
echo.

echo Aktualni stav:
git status
echo.

echo Pridavam vsechny soubory...
git add .

git diff --staged --quiet
if %ERRORLEVEL% NEQ 0 (
  echo.
  set /p commit_msg="Popis zmen (Enter = 'Update'): "
  if "!commit_msg!"=="" set commit_msg=Update
  git commit -m "!commit_msg!"
  if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [CHYBA] Commit se nepovedl. Zkontrolujte hlasku vyse.
    pause
    exit /b 1
  )
  echo.
) else (
  echo Zadne zmeny k commitovani - pujde jen push.
  echo.
)

echo Odesilam na GitHub...
git push origin main
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [CHYBA] Push se nepovedl. Pokud to chce prihlaseni, bude potreba nastavit pristup (token/SSH).
  pause
  exit /b 1
)

echo.
echo ==========================================
echo      HOTOVO - ZMENY JSOU ONLINE
echo ==========================================
pause

