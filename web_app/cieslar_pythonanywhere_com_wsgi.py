# WSGI pro cieslar.pythonanywhere.com – PDF DokuCheck Web
# Cesta: /home/cieslar/web_app/web_app/wsgi_pythonanywhere.py (nebo tento soubor)

import sys
import os

path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.insert(0, path)
os.chdir(path)

from pdf_check_web_main import app as application
