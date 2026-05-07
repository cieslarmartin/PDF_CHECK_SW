@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

echo ============================================================
echo   DokuCheck – prihlaseni na GitHub a push (automat) – V1
echo ============================================================
echo.

cd /d "%~dp0"

echo Repo:
for /f "delims=" %%A in ('git remote get-url origin 2^>nul') do set "ORIGIN_URL=%%A"
if not defined ORIGIN_URL (
  echo [CHYBA] V tomhle adresari neni git repozitar (nebo chybi remote origin).
  pause
  exit /b 1
)
echo   origin = !ORIGIN_URL!
echo.

REM --- 1) Zajistit GitHub CLI (gh) ---
where gh >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo [INFO] GitHub CLI (gh) neni nainstalovan. Instalace pres winget...
  where winget >nul 2>&1
  if %ERRORLEVEL% NEQ 0 (
    echo [CHYBA] winget neni k dispozici.
    echo Nainstalujte "GitHub CLI" rucne (GitHub CLI) nebo doinstalujte winget.
    pause
    exit /b 1
  )
  winget install --id GitHub.cli
  if %ERRORLEVEL% NEQ 0 (
    echo [CHYBA] Instalace gh selhala.
    pause
    exit /b 1
  )
  echo.
  echo [OK] gh nainstalovano. Pokud to stale nejde, zavrete a znovu otevrete okno terminalu.
  echo.
)

REM --- 2) Prihlaseni do GitHubu (otevre prohlizec) ---
echo Spoustim prihlaseni do GitHubu...
echo Vyberte: GitHub.com ^> HTTPS ^> Login with a web browser
echo Prihlaste se jako ucet, ktery ma pristup do repozitare.
echo.
gh auth login
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [CHYBA] Prihlaseni selhalo nebo bylo zruseno.
  pause
  exit /b 1
)

echo.
echo Ověřuji přihlášení:
gh auth status
echo.

REM --- 3) Push ---
echo Odesilam zmeny na GitHub...
git push origin main
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [CHYBA] Push se nepovedl.
  echo Tip: Pokud hlasi 403 / spatny ucet, odhlaste se a prihlaste spravnym uctem:
  echo   gh auth logout -h github.com
  echo   gh auth login
  pause
  exit /b 1
)

echo.
echo ============================================================
echo   HOTOVO – push na origin/main probehl uspesne
echo ============================================================
pause

