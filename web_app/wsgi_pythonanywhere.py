# WSGI pro PythonAnywhere – PDF DokuCheck Web (cieslar)
# Tento soubor musí být v téže složce jako pdf_check_web_main.py.
# Na PA: Source code = Working directory = /home/cieslar/web_app/web_app
# Cesta k tomuto souboru: /home/cieslar/web_app/web_app/wsgi_pythonanywhere.py

import sys
import os

# Složka, kde leží pdf_check_web_main.py (stejná jako tento soubor)
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.insert(0, path)
os.chdir(path)

from pdf_check_web_main import app as application
