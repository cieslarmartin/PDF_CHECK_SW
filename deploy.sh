#!/bin/bash
# =============================================================================
# Deploy na PythonAnywhere – vynucení čistého stavu z origin/main
# Lze spustit:  bash deploy.sh  (z kořene repozitáře)  nebo  ~/deploy.sh
# Při spuštění z jiného místa lze nastavit:  export REPO_ROOT=~/web_app; export VENV=~/web_app-virtualenv
# =============================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Kořen repozitáře: env REPO_ROOT, nebo auto (skript v ~ a repo v ~/web_app nebo ~/web_app/web_app)
REPO_ROOT="${REPO_ROOT:-$SCRIPT_DIR}"
if [ ! -f "$REPO_ROOT/web_app/requirements.txt" ]; then
  if [ -f "$SCRIPT_DIR/web_app/web_app/requirements.txt" ]; then
    REPO_ROOT="$SCRIPT_DIR/web_app"
  elif [ -f "$SCRIPT_DIR/web_app/web_app/web_app/requirements.txt" ]; then
    REPO_ROOT="$SCRIPT_DIR/web_app/web_app"
  fi
fi
cd "$REPO_ROOT" || exit 1

if [ ! -f "$REPO_ROOT/web_app/requirements.txt" ]; then
  echo "CHYBA: Nenalezen web_app/requirements.txt v $REPO_ROOT"
  echo "Nastavte kořen repozitáře: export REPO_ROOT=/home/VASE_JMENO/web_app   (nebo kde máte .git a složku web_app)"
  exit 1
fi

# Virtuální prostředí na PA (typicky ~/web_app-virtualenv nebo ~/venv)
VENV="${VENV:-$HOME/web_app-virtualenv}"
if [ -d "$REPO_ROOT/venv" ]; then
  VENV="$REPO_ROOT/venv"
fi
if [ ! -f "$VENV/bin/activate" ]; then
  echo "CHYBA: Nenalezen venv: $VENV"
  echo "Nastavte: export VENV=/home/VASE_JMENO/web_app-virtualenv"
  exit 1
fi

DB_PATH="web_app/pdfcheck_results.db"
if [ -f "$REPO_ROOT/$DB_PATH" ]; then
  echo "[0] Záloha databáze (zachová lokální data na PA)"
  cp "$REPO_ROOT/$DB_PATH" /tmp/pdfcheck_results.db.bak
fi

echo "[1] Git: fetch + reset na origin/main (repo: $REPO_ROOT)"
git fetch --all
git reset --hard origin/main

if [ -f /tmp/pdfcheck_results.db.bak ]; then
  echo "[1b] Obnovení databáze ze zálohy"
  cp /tmp/pdfcheck_results.db.bak "$REPO_ROOT/$DB_PATH"
fi

echo "[2] Aktivace venv a instalace závislostí ($VENV)"
# shellcheck source=/dev/null
source "$VENV/bin/activate"
pip install -q -r "$REPO_ROOT/web_app/requirements.txt"

echo "[3] Restart WSGI (touch)"
touch "$REPO_ROOT/web_app/wsgi_pythonanywhere.py"

echo "Deploy dokončen."
