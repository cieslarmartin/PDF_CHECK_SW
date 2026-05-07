@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

echo ============================================================
echo   DokuCheck – prihlaseni na GitHub a push (automat) – V1
echo ============================================================
echo.

cd /d "%~dp0"

echo Repo:
set "ORIGIN_URL="
setlocal DisableDelayedExpansion
for /f "usebackq delims=" %%A in (`git remote get-url origin 2^>nul`) do set "ORIGIN_URL=%%A"
endlocal & set "ORIGIN_URL=%ORIGIN_URL%"
if not defined ORIGIN_URL goto :NO_ORIGIN
echo   origin = %ORIGIN_URL%
echo.

REM --- Najdi gh.exe (i kdyz PATH jeste neni obnovena) ---
set "GH_EXE="
for /f "delims=" %%G in ('where gh 2^>nul') do (
  if not defined GH_EXE set "GH_EXE=%%G"
)
if not defined GH_EXE (
  if exist "%ProgramFiles%\GitHub CLI\gh.exe" set "GH_EXE=%ProgramFiles%\GitHub CLI\gh.exe"
)
if not defined GH_EXE (
  if exist "%LocalAppData%\Programs\GitHub CLI\gh.exe" set "GH_EXE=%LocalAppData%\Programs\GitHub CLI\gh.exe"
)

REM --- 1) Zajistit GitHub CLI (gh) ---
if not defined GH_EXE where gh >nul 2>&1
if errorlevel 1 (
  echo [INFO] GitHub CLI - prikaz "gh" neni nainstalovan. Instalace pres winget...
  where winget >nul 2>&1
  if errorlevel 1 (
    echo [CHYBA] winget neni k dispozici.
    echo Nainstalujte "GitHub CLI" rucne nebo doinstalujte winget.
    pause
    exit /b 1
  )
  winget install --id GitHub.cli
  if errorlevel 1 (
    echo [CHYBA] Instalace gh selhala.
    pause
    exit /b 1
  )
  echo.
  echo [OK] gh nainstalovano. Hledam gh.exe...
  echo.

  set "GH_EXE="
  for /f "delims=" %%G in ('where gh 2^>nul') do (
    if not defined GH_EXE set "GH_EXE=%%G"
  )
  if not defined GH_EXE (
    if exist "%ProgramFiles%\GitHub CLI\gh.exe" set "GH_EXE=%ProgramFiles%\GitHub CLI\gh.exe"
  )
  if not defined GH_EXE (
    if exist "%LocalAppData%\Programs\GitHub CLI\gh.exe" set "GH_EXE=%LocalAppData%\Programs\GitHub CLI\gh.exe"
  )
  if not defined GH_EXE (
    echo [CHYBA] gh je nainstalovane, ale nelze najit gh.exe.
    echo Zkuste zavrit a znovu otevrit okno CMD a spustit skript znovu.
    pause
    exit /b 1
  )
)

REM --- 2) Prihlaseni do GitHubu (otevre prohlizec) ---
echo Kontroluji prihlaseni do GitHubu...
"%GH_EXE%" auth status >nul 2>&1
if errorlevel 1 (
  echo [INFO] Nejste prihlaseni do GitHubu v tomto PC.
  echo Spustim jednorazove prihlaseni (otevre se prohlizec).
  echo Vyberte: GitHub.com ^> HTTPS ^> Login with a web browser
  echo Prihlaste se jako ucet, ktery ma pristup do repozitare.
  echo.
  "%GH_EXE%" auth login
  if errorlevel 1 (
    echo.
    echo [CHYBA] Prihlaseni selhalo nebo bylo zruseno.
    pause
    exit /b 1
  )
) else (
  echo [OK] Prihlaseni je uz hotove - nebudu nic potvrzovat.
)

echo.
echo Ověřuji přihlášení:
"%GH_EXE%" auth status
echo.

REM --- 3) Push ---
echo Odesilam zmeny na GitHub...
git push origin main
if errorlevel 1 (
  echo.
  echo [CHYBA] Push se nepovedl.
  echo Tip: Pokud hlasi 403 / spatny ucet, odhlaste se a prihlaste spravnym uctem:
  echo   "%GH_EXE%" auth logout -h github.com
  echo   "%GH_EXE%" auth login
  pause
  exit /b 1
)

echo.
echo ============================================================
echo   HOTOVO – push na origin/main probehl uspesne
echo ============================================================
pause

exit /b 0

:NO_ORIGIN
echo [CHYBA] V tomhle adresari neni git repozitar (nebo chybi remote origin).
pause
exit /b 1

