@echo off
echo ==========================================
echo      ODESILANI ZMEN NA GITHUB (PUSH)
echo ==========================================
echo.
git status
echo.
echo Pridavam vsechny soubory...
git add .
echo.
set /p commit_msg="Napis popis zmen (co jsi udelal): "
git commit -m "%commit_msg%"
echo.
echo Odesilam na GitHub...
git push origin main
echo.
echo ==========================================
echo      HOTOVO - ZMENY JSOU ONLINE
echo ==========================================
pause
