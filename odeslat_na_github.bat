@echo off
setlocal enabledelayedexpansion
echo ==========================================
echo      ODESILANI ZMEN NA GITHUB (PUSH)
echo ==========================================
echo.
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
  echo.
) else (
  echo Zadne zmeny k commitovani - pujde jen push.
  echo.
)
echo Odesilam na GitHub...
git push origin main
echo.
echo ==========================================
echo      HOTOVO - ZMENY JSOU ONLINE
echo ==========================================
pause
