@echo off
cd /d "%~dp0.."
python store\build_msix.py %*
pause
