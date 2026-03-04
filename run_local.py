# run_local.py – lokální testovací prostředí (neovlivňuje wsgi ani PythonAnywhere)
# Spouštění z kořene projektu: python run_local.py
# Otevři v prohlížeči: http://127.0.0.1:8080

import os
import sys

# Kořen projektu v sys.path, aby fungoval import web_app
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

from web_app.pdf_check_web_main import app

if __name__ == '__main__':
    app.config['DEBUG'] = True
    print("--- SPUŠTĚNO LOKÁLNÍ TESTOVACÍ PROSTŘEDÍ ---")
    print("Adresa: http://127.0.0.1:8080")
    print("Pro ukončení stiskněte CTRL+C")
    print("--------------------------------------------")
    app.run(host='127.0.0.1', port=8080, debug=True)
