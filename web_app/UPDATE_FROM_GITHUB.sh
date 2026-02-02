#!/bin/bash
# ============================================================
# Skript pro PythonAnywhere - stáhne změny z GitHubu
# Spusťte v Bash konzoli: bash ~/pdf-dokucheck-web/v42/UPDATE_FROM_GITHUB.sh
# ============================================================

echo "========================================"
echo "  Aktualizace z GitHubu"
echo "========================================"

cd ~/pdf-dokucheck-web

echo "[1/2] Stahuji změny z GitHubu..."
git fetch origin
git reset --hard origin/main

echo ""
echo "[2/2] Hotovo!"
echo ""
echo "Nezapomeňte kliknout na RELOAD ve Web tabu!"
echo "========================================"
