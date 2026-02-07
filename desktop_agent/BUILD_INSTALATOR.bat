@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Spouštím build instalátoru...
echo.
python build_installer.py
echo.
pause
