#!/bin/bash
# =============================================================================
# Deploy na PythonAnywhere – cieslar
# Struktura: /home/cieslar/web_app (root s .git) → web_app/ (aplikace, requirements, wsgi)
# Venv: /home/cieslar/web_app/venv
#
# Použití na PA v Bash (vždy z kořene klonu, ne z ~/):
#   cd /home/cieslar/web_app && bash deploy.sh
# =============================================================================

set -e

# Kořen klonu = složka, kde leží tento soubor (funguje i při volání bash /abs/path/deploy.sh)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f "$SCRIPT_DIR/web_app/pdf_check_web_main.py" ]]; then
  echo "CHYBA: deploy.sh musí být v kořeni klonu PDF_CHECK_SW (vedle web_app/)."
  echo "        Aktuální: $SCRIPT_DIR"
  echo "        Správně:  cd /home/USERNAME/PDF_CHECK_SW   # nebo /home/cieslar/web_app"
  echo "                  bash deploy.sh"
  echo "  (Nespouštějte kopii deploy.sh z domovské složky ~/ — ta nemusí obsahovat kontroly enginu.)"
  exit 1
fi
REPO_ROOT="${REPO_ROOT:-$SCRIPT_DIR}"
VENV="${VENV:-$REPO_ROOT/venv}"
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

if [ -f "$REPO_ROOT/version.py" ]; then
  echo "VAROVÁNÍ: Existuje $REPO_ROOT/version.py — může stínit web_app/version.py a držet starý WEB_BUILD. Soubor smažte nebo přejmenujte."
fi

if [ -f /tmp/pdfcheck_results.db.bak ]; then
  echo "[1b] Obnovení databáze ze zálohy"
  cp /tmp/pdfcheck_results.db.bak "$DB_PATH"
fi

echo "[2] Aktivace venv a instalace závislostí"
# shellcheck source=/dev/null
source "$VENV/bin/activate"
pip install -q -r "$APP_DIR/requirements.txt"

if [ ! -d "$REPO_ROOT/desktop_agent" ]; then
  echo "CHYBA: Chybí $REPO_ROOT/desktop_agent — cloudová kontrola PDF na webu potřebuje sdílený engine z celého klonu repa."
  exit 1
fi

echo "[3] Kontrola importů (stejné pořadí cest jako ve web_app po startu)"
export DEPLOY_CHECK_ROOT="$REPO_ROOT"
export DEPLOY_CHECK_APP="$APP_DIR"
python << 'PYCHECK'
import os
import sys

root = os.environ["DEPLOY_CHECK_ROOT"]
app = os.environ["DEPLOY_CHECK_APP"]
sys.path.insert(0, app)
sys.path.append(root)
import version as v
print("    version:", v.WEB_VERSION, "build=", v.WEB_BUILD)
try:
    from desktop_agent import pdf_checker as _pc
    assert _pc is not None
    print("    desktop_agent.pdf_checker: OK")
except Exception as e:
    print("    CHYBA importu engine:", type(e).__name__, e)
    print("    Záložka Web na PA musí používat WSGI:", os.path.join(app, "wsgi_pythonanywhere.py"))
    sys.exit(1)
PYCHECK

echo "[4] Restart WSGI (touch – PA načte nový kód)"
touch "$WSGI_FILE"

echo "Deploy dokončen."
echo "  → PythonAnywhere: záložka Web → ověřte WSGI file = $WSGI_FILE → klikněte Reload."
echo "  → Ověřte https://www.dokucheck.cz/__diag (JSON, web_build musí odpovídat version.py)."
echo "  → V logu výše musí být řádky „[3] Kontrola importů“ a „desktop_agent.pdf_checker: OK“."
