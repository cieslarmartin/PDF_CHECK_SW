#!/bin/bash
# PythonAnywhere: obnovení virtuálního prostředí na Python 3.10 (oprava "3.13 instead of 3.10")
# Spusťte na PA v adresáři projektu (např. ~/pdf-dokucheck-web nebo ~/PDF_CHECK_SW/web_app)

set -e
echo "=== Odstraňuji starý venv ==="
rm -rf venv
echo "=== Vytvářím venv s Python 3.10 ==="
virtualenv -p python3.10 venv
echo "=== Aktivace venv ==="
source venv/bin/activate
echo "=== Python verze ==="
python --version
if ! python -c "import sys; exit(0 if sys.version_info[:2] == (3, 10) else 1)"; then
    echo "CHYBA: Očekáván Python 3.10.x. Nainstalujte: pa_install_python 3.10"
    exit 1
fi
echo "=== Instalace závislostí ==="
pip install --upgrade pip
pip install -r requirements.txt
echo "=== Hotovo. Ověřte: python --version (mělo by být 3.10.x) ==="
