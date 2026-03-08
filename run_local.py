# run_local.py – lokální testovací prostředí (neovlivňuje wsgi ani PythonAnywhere)
# Spouštění z kořene projektu: python run_local.py
# Otevři v prohlížeči: http://127.0.0.1:8080  nebo  http://127.0.0.1:8080/landing-preview

import os
import sys
import threading
import webbrowser

# Cesty: kořen projektu + složka web_app (kvůli importům api_endpoint, database, ...)
_root = os.path.dirname(os.path.abspath(__file__))
_web_app = os.path.join(_root, 'web_app')
if _root not in sys.path:
    sys.path.insert(0, _root)
if _web_app not in sys.path:
    sys.path.insert(0, _web_app)
os.chdir(_root)

try:
    from web_app.pdf_check_web_main import app
except Exception as e:
    import traceback
    print("Chyba pri startu:")
    traceback.print_exc()
    input("\nStiskni Enter pro ukonceni...")
    sys.exit(1)

if __name__ == '__main__':
    app.config['DEBUG'] = True
    print("--- SPUSTENO LOKALNI TESTOVACI PROSTREDI (offline) ---")
    print("  Web:        http://127.0.0.1:8080/")
    print("  Nahled A-E: http://127.0.0.1:8080/landing-preview")
    print("  (Varianty:  ?v=a | ?v=b | ?v=c | ?v=d | ?v=e)")
    print("  Pro ukonceni stisknete CTRL+C (okno nechte otevrene)")
    print("--------------------------------------------------------")

    def open_preview():
        webbrowser.open('http://127.0.0.1:8080/landing-preview')
    threading.Timer(1.5, open_preview).start()

    app.run(host='127.0.0.1', port=8080, debug=True)
