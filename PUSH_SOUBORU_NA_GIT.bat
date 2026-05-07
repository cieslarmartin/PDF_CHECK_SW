@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

echo ============================================================
echo   DokuCheck – PUSH SOUBORU NA GIT (origin/main)
echo ============================================================
echo.

cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 (
  echo [CHYBA] Git neni nainstalovan nebo neni v PATH.
  echo Nainstalujte Git pro Windows a zkuste znovu.
  pause
  exit /b 1
)

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo [CHYBA] Tohle neni git repozitar.
  pause
  exit /b 1
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
  echo [CHYBA] Chybi remote "origin".
  pause
  exit /b 1
)

echo Aktualni stav:
git status
echo.

echo Pridavam soubory...
git add .
echo.

git diff --staged --quiet
if errorlevel 1 (
  set /p commit_msg="Popis zmen (Enter = 'Update'): "
  if "!commit_msg!"=="" set "commit_msg=Update"
  echo.
  echo Commituji: "!commit_msg!"
  git commit -m "!commit_msg!"
  if errorlevel 1 (
    echo.
    echo [CHYBA] Commit se nepovedl. Zkontrolujte hlasku vyse.
    pause
    exit /b 1
  )
) else (
  echo Zadne zmeny k commitovani - provedu jen push.
)

echo.
echo Odesilam na GitHub...
git push origin main
if errorlevel 1 (
  echo.
  echo [CHYBA] Push se nepovedl. Pokud to chce prihlaseni, nastavte pristup (token/SSH).
  pause
  exit /b 1
)

echo.
echo ============================================================
echo   HOTOVO – zmeny jsou na GitHubu (origin/main)
echo ============================================================
pause
exit /b 0

