# test_converter.py
# Jednoduchý test PDF Converter modulu
# Build 1.0 | © 2025 Ing. Martin Cieślar

import os
import sys
from pathlib import Path

# Přidáme parent do sys.path pro správný import
sys.path.insert(0, str(Path(__file__).parent.parent))

from pdf_converter import (
    remove_signatures,
    convert_to_pdfa,
    process_pdf_batch,
    ProcessingOptions
)
from pdf_converter.pdfa_converter import find_ghostscript


def test_ghostscript():
    """Test dostupnosti Ghostscriptu"""
    print("=" * 50)
    print("TEST: Ghostscript")
    print("=" * 50)

    gs_path = find_ghostscript()
    if gs_path:
        print(f"✓ Ghostscript nalezen: {gs_path}")
        return True
    else:
        print("✗ Ghostscript NENALEZEN!")
        print("\nPro Windows stáhněte z: https://ghostscript.com/download/gsdnld.html")
        print("Pro instalaci doporučujeme verzi 'Ghostscript AGPL Release'")
        return False


def test_signature_removal(input_pdf: str, output_dir: str):
    """Test odstranění podpisů"""
    print("\n" + "=" * 50)
    print("TEST: Odstranění podpisů")
    print("=" * 50)

    if not os.path.exists(input_pdf):
        print(f"✗ Vstupní soubor neexistuje: {input_pdf}")
        return False

    output_path = os.path.join(output_dir, "test_unsigned.pdf")
    success, message = remove_signatures(input_pdf, output_path)

    if success:
        print(f"✓ {message}")
        print(f"  Výstup: {output_path}")
        return True
    else:
        print(f"✗ {message}")
        return False


def test_pdfa_conversion(input_pdf: str, output_dir: str):
    """Test konverze na PDF/A"""
    print("\n" + "=" * 50)
    print("TEST: Konverze na PDF/A-3B")
    print("=" * 50)

    if not os.path.exists(input_pdf):
        print(f"✗ Vstupní soubor neexistuje: {input_pdf}")
        return False

    output_path = os.path.join(output_dir, "test_pdfa3b.pdf")
    success, message = convert_to_pdfa(input_pdf, output_path, pdfa_version="3", conformance="B")

    if success:
        print(f"✓ {message}")
        print(f"  Výstup: {output_path}")
        return True
    else:
        print(f"✗ {message}")
        return False


def test_batch_processing(input_folder: str, output_dir: str):
    """Test dávkového zpracování"""
    print("\n" + "=" * 50)
    print("TEST: Dávkové zpracování")
    print("=" * 50)

    if not os.path.exists(input_folder):
        print(f"✗ Složka neexistuje: {input_folder}")
        return False

    # Najdeme PDF soubory
    pdf_files = [str(f) for f in Path(input_folder).glob("*.pdf")]

    if not pdf_files:
        print(f"✗ Ve složce nejsou žádné PDF soubory: {input_folder}")
        return False

    print(f"  Nalezeno {len(pdf_files)} PDF souborů")

    # Nastavení
    options = ProcessingOptions(
        remove_signatures=True,
        convert_to_pdfa=True,
        pdfa_version="3",
        pdfa_conformance="B",
        output_dir=output_dir,
        overwrite=False,
        max_workers=2
    )

    # Progress callback
    def progress(current, total, filename):
        print(f"  [{current}/{total}] {filename}")

    # Zpracování
    results = process_pdf_batch(pdf_files, options, progress)

    # Výsledky
    success_count = sum(1 for r in results if r.success)
    print(f"\n  Výsledek: {success_count}/{len(results)} úspěšně")

    for r in results:
        status = "✓" if r.success else "✗"
        print(f"  {status} {Path(r.input_file).name}")
        for step in r.steps:
            print(f"      {step}")
        if r.error:
            print(f"      CHYBA: {r.error}")

    return success_count == len(results)


def main():
    """Hlavní test"""
    print("\n" + "=" * 60)
    print("   PDF CONVERTER - TEST SUITE")
    print("   Fáze 1: Odstranění podpisů + Konverze na PDF/A")
    print("=" * 60)

    # Test Ghostscriptu
    gs_ok = test_ghostscript()

    if not gs_ok:
        print("\n⚠ Bez Ghostscriptu nelze konvertovat na PDF/A!")
        print("  Odstranění podpisů bude fungovat.")

    # Pokud máme argumenty, použijeme je
    if len(sys.argv) >= 2:
        input_path = sys.argv[1]
        output_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(input_path)

        os.makedirs(output_dir, exist_ok=True)

        if os.path.isdir(input_path):
            # Dávkové zpracování
            test_batch_processing(input_path, output_dir)
        else:
            # Jeden soubor
            test_signature_removal(input_path, output_dir)
            if gs_ok:
                test_pdfa_conversion(input_path, output_dir)
    else:
        print("\n" + "-" * 50)
        print("Použití:")
        print("  python test_converter.py <pdf_soubor> [výstupní_složka]")
        print("  python test_converter.py <složka_s_pdf> [výstupní_složka]")
        print("\nPříklad:")
        print("  python test_converter.py C:/Documents/test.pdf C:/Output")
        print("  python test_converter.py C:/Documents/PDFs C:/Output")

    print("\n" + "=" * 60)
    print("   TEST DOKONČEN")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
