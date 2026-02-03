#!/bin/bash
# =============================================================================
# Deploy na PythonAnywhere – vynucení čistého stavu z origin/main
# Spusťte na PA v Bash z kořene repozitáře:  bash deploy.sh
# Předpoklad: venv v domovském adresáři nebo v projektu (upravte cestu VENV níže)
# =============================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR" && pwd)"
cd "$REPO_ROOT" || exit 1

# Cesta k virtuálnímu prostředí na PA (typicky ~/venv nebo ~/PDF_CHECK_SW/venv)
VENV="${VENV:-$HOME/venv}"
if [ -d "$REPO_ROOT/venv" ]; then
  VENV="$REPO_ROOT/venv"
fi

echo "[1] Git: fetch + reset na origin/main"
git fetch --all
git reset --hard origin/main

echo "[2] Aktivace venv a instalace závislostí"
# shellcheck source=/dev/null
source "$VENV/bin/activate"
pip install -q -r web_app/requirements.txt

echo "[3] Restart WSGI (touch)"
touch "$REPO_ROOT/web_app/wsgi_pythonanywhere.py"

echo "Deploy dokončen."
