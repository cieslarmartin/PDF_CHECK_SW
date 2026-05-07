# WSGI pro PythonAnywhere – PDF DokuCheck Web (cieslar)
# Tento soubor musí být v téže složce jako pdf_check_web_main.py.
# Na PA: např. REPO_ROOT=/home/cieslar/web_app, tento soubor v .../web_app/wsgi_pythonanywhere.py
# Pozor: nesmí existovat soubor version.py přímo v REPO_ROOT – přepisoval by web_app/version.py při špatném sys.path.

import sys
import os

# Složka, kde leží pdf_check_web_main.py (stejná jako tento soubor)
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.insert(0, path)
os.chdir(path)

from pdf_check_web_main import app as application
