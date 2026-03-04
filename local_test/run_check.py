# run_check.py - kontrola PDF bez spuštění webu (pouze logika z desktop_agent/pdf_checker)
# Použití:
#   python local_test/run_check.py                    -> zkontroluje všechna PDF v local_test/pdfs/
#   python local_test/run_check.py "cesta\k\file.pdf" -> zkontroluje jeden soubor
# Spouštěj z kořene projektu: c:\Claude\PDF_CHECK_SW

import os
import sys
import json

# Kořen projektu
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

# Import z agenta (stejná logika jako web po úpravách)
sys.path.insert(0, os.path.join(_root, 'desktop_agent'))
from pdf_checker import analyze_pdf_file

def main():
    pdfs_dir = os.path.join(_root, 'local_test', 'pdfs')
    if len(sys.argv) >= 2:
        path = sys.argv[1]
        if not os.path.isfile(path):
            print("Chyba: soubor neexistuje:", path)
            sys.exit(1)
        paths = [path]
    else:
        if not os.path.isdir(pdfs_dir):
            os.makedirs(pdfs_dir, exist_ok=True)
            print("Složka local_test/pdfs/ vytvořena. Vlož sem PDF a spusť skript znovu.")
            sys.exit(0)
        paths = [os.path.join(pdfs_dir, f) for f in os.listdir(pdfs_dir) if f.lower().endswith('.pdf')]
        if not paths:
            print("V local_test/pdfs/ nejsou žádná PDF. Přidej soubory nebo spusť: python local_test/run_check.py \"cesta\\k\\soubor.pdf\"")
            sys.exit(0)

    print("--- Lokální kontrola PDF (bez webu) ---")
    for path in paths:
        print("\nSoubor:", path)
        result = analyze_pdf_file(path)
        if result.get('success'):
            sigs = result.get('results', {}).get('signatures', [])
            print("  Úspěch | Podpisů:", len(sigs), "| PDF/A:", result.get('results', {}).get('pdf_format', {}).get('exact_version', '—'))
            for s in sigs:
                print("   -", s.get('type', '?'), "|", s.get('name', '—'))
        else:
            print("  Chyba:", result.get('error', '?'))
    print("\n--- Konec ---")

if __name__ == '__main__':
    main()
