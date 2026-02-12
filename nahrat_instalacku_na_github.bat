@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo.
echo ==========================================
echo   NAHRANI INSTALACKY NA GITHUB RELEASES
echo ==========================================
echo.

REM --- 1. Overeni, ze gh CLI je dostupne ---
where gh >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [CHYBA] GitHub CLI (gh) neni nainstalovan.
    echo Nainstalujte: winget install --id GitHub.cli
    pause
    exit /b 1
)

REM --- 2. Overeni prihlaseni ---
gh auth status >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Nejste prihlaseni do GitHubu. Spoustim prihlaseni...
    echo Zvolte: GitHub.com, HTTPS, prihlaseni pres prohlizec.
    echo.
    gh auth login
    if %ERRORLEVEL% NEQ 0 (
        echo [CHYBA] Prihlaseni selhalo.
        pause
        exit /b 1
    )
)
echo [OK] GitHub CLI prihlaseno.
echo.

REM --- 3. Nalezeni nejnovejsiho .exe v desktop_agent\install ---
set "INSTALL_DIR=desktop_agent\install"
set "EXE_FILE="
for /f "delims=" %%F in ('dir /b /o-d "%INSTALL_DIR%\*.exe" 2^>nul') do (
    if not defined EXE_FILE set "EXE_FILE=%%F"
)

if not defined EXE_FILE (
    echo [CHYBA] Zadny .exe soubor nenalezen v %INSTALL_DIR%\
    echo Nejprve spustte build (build_installer.py).
    pause
    exit /b 1
)

echo Nalezena instalacka: %EXE_FILE%
echo.

REM --- 4. Zjisteni verze z nazvu souboru (DokuCheckPRO_Setup_46_2026-02-12.exe -> v46) ---
set "TAG="
for /f "tokens=3 delims=_" %%V in ("%EXE_FILE%") do set "TAG=v%%V"
if not defined TAG set "TAG=v0"

echo Tag releasu: %TAG%
echo.

REM --- 5. Overeni, ze release s timto tagem jeste neexistuje (pokud ano, smazeme a vytvorime znovu) ---
gh release view %TAG% >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Release %TAG% uz existuje - nahrazuji soubor...
    gh release delete-asset %TAG% "%EXE_FILE%" --yes >nul 2>&1
    gh release upload %TAG% "%INSTALL_DIR%\%EXE_FILE%" --clobber
) else (
    echo Vytvarim novy release %TAG%...
    gh release create %TAG% "%INSTALL_DIR%\%EXE_FILE%" --title "DokuCheck %TAG%" --notes "Instalacni soubor DokuCheck pro Windows.  Stahujte soubor %EXE_FILE%." --latest
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [CHYBA] Nahrani selhalo. Zkontrolujte pripojeni a prihlaseni (gh auth status).
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   HOTOVO - INSTALACKA JE NA GITHUBU
echo ==========================================
echo.
echo URL releasu:
gh release view %TAG% --json url --jq .url
echo.
echo URL primo ke stazeni .exe:
gh release view %TAG% --json assets --jq ".assets[0].url"
echo.
echo Tento odkaz nastavte v Admin panelu jako "download_url".
echo.
pause
