#!/bin/bash
# =============================================================================
# Deploy na PythonAnywhere – cieslar
# Struktura: /home/cieslar/web_app (root s .git) → web_app/ (aplikace, requirements, wsgi)
# Venv: /home/cieslar/web_app/venv
#
# Použití na PA v Bash:  cd /home/cieslar/web_app && bash deploy.sh
# Nebo z domova:  bash /home/cieslar/web_app/deploy.sh
# =============================================================================

set -e

REPO_ROOT="${REPO_ROOT:-/home/cieslar/web_app}"
VENV="${VENV:-/home/cieslar/web_app/venv}"
# Složka s aplikací (pdf_check_web_main.py, requirements.txt, wsgi)
APP_DIR="$REPO_ROOT/web_app"
DB_PATH="$APP_DIR/pdfcheck_results.db"
WSGI_FILE="$APP_DIR/wsgi_pythonanywhere.py"

cd "$REPO_ROOT" || { echo "CHYBA: Nelze přejít do $REPO_ROOT"; exit 1; }

if [ ! -f "$APP_DIR/requirements.txt" ]; then
  echo "CHYBA: Nenalezen $APP_DIR/requirements.txt"
  echo "Nastavte REPO_ROOT (např. export REPO_ROOT=/home/cieslar/web_app)"
  exit 1
fi

if [ ! -f "$VENV/bin/activate" ]; then
  echo "CHYBA: Nenalezen venv: $VENV"
  echo "Nastavte VENV (např. export VENV=/home/cieslar/web_app/venv)"
  exit 1
fi

echo "[0] Záloha databáze (zachová lokální data na PA)"
if [ -f "$DB_PATH" ]; then
  cp "$DB_PATH" /tmp/pdfcheck_results.db.bak
else
  echo "    (databáze zatím neexistuje)"
fi

echo "[1] Git: fetch + reset na origin/main"
git fetch origin main
git reset --hard origin/main

if [ -f /tmp/pdfcheck_results.db.bak ]; then
  echo "[1b] Obnovení databáze ze zálohy"
  cp /tmp/pdfcheck_results.db.bak "$DB_PATH"
fi

echo "[2] Aktivace venv a instalace závislostí"
# shellcheck source=/dev/null
source "$VENV/bin/activate"
pip install -q -r "$APP_DIR/requirements.txt"

echo "[3] Restart WSGI (touch – PA načte nový kód)"
touch "$WSGI_FILE"

echo "Deploy dokončen. V záložce Web na PA klikněte Reload, pokud se stránka sama neobnoví."
