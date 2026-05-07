@echo off
title DokuCheck – lokální test
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_local_test.ps1"
echo.
pause
