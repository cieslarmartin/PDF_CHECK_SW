# -*- coding: utf-8 -*-
"""
Jedna dávka: aktuální desktop agent → .exe instalátor + .msix pro Store.

Pořadí (jednou PyInstaller):
  1) PyInstaller → dist/DokuCheckPRO/
  2) MSIX  → store/output/DokuCheck_{BUILD}.msix
  3) Inno  → install/DokuCheckPRO_Setup_{BUILD}_{datum}.exe
  4) Úklid build/ a dist/

Spouštění z desktop_agent:
  python build_exe_and_msix.py
  BUILD_EXE_A_MSIX.bat
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STORE_BUILD = os.path.join(SCRIPT_DIR, "store", "build_msix.py")


def main():
    parser = argparse.ArgumentParser(
        description="Build DokuCheck: exe instalátor + MSIX (stejný build z version.py)"
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=os.environ.get("DOKUCHECK_INSTALL_OUTPUT", "").strip(),
        metavar="CESTA",
        help="Volitelná kopie .exe instalátoru (navíc k install/).",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.strip() if args.output_dir else None

    os.chdir(SCRIPT_DIR)
    sys.path.insert(0, SCRIPT_DIR)

    import build_installer as bi

    # store/build_msix.py jako modul
    store_dir = os.path.join(SCRIPT_DIR, "store")
    if store_dir not in sys.path:
        sys.path.insert(0, store_dir)
    import build_msix as msix  # type: ignore

    print("=== Build EXE + MSIX (stejný build) ===\n")
    if output_dir:
        print(f"Kopie instalátoru také do: {os.path.abspath(output_dir)}\n")

    print("Kontrola závislostí…")
    bi.check_pyinstaller()
    iscc = bi.find_iscc()
    makeappx = msix.find_makeappx()
    print(f"  PyInstaller: OK")
    print(f"  Inno Setup:  {iscc}")
    print(f"  makeappx:    {makeappx}\n")

    build, msix_version = msix.detect_versions()
    print(f"BUILD_VERSION: {build}")
    print(f"MSIX Identity Version: {msix_version}\n")

    print("Krok 1/4: PyInstaller (jednou pro oba výstupy)…")
    bi.run_pyinstaller()

    print("\nKrok 2/4: MSIX pro Microsoft Store…")
    msix.ensure_assets()
    msix.build_staging(msix_version)
    os.makedirs(msix.OUTPUT_DIR, exist_ok=True)
    msix_name = f"DokuCheck_{build}.msix"
    msix_path = os.path.join(msix.OUTPUT_DIR, msix_name)
    print(f"  Balím: {msix_path}")
    msix.pack_msix(msix_path)

    print("\nKrok 3/4: Inno Setup (testovací .exe)…")
    bi.run_inno_setup(build)
    exe_path = bi.finalize_installer(build, output_dir=output_dir)

    print("\nKrok 4/4: Úklid build/ a dist/…")
    bi.clean_build_dirs()

    print("\n========== HOTOVO ==========")
    print(f"  Testujte tento EXE:  {exe_path}")
    print(f"  Pak nahrajte MSIX:   {msix_path}")
    print(f"  Build:               {build}  |  MSIX verze: {msix_version}")
    print("============================\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        print("\n--- CHYBA ---")
        traceback.print_exc()
        print(
            "\nPotřebujete: PyInstaller, Inno Setup 6, Windows SDK (makeappx).\n"
            "Samostatně: BUILD_INSTALATOR.bat | store\\BUILD_MSIX.bat"
        )
        try:
            input("Stiskněte Enter pro ukončení…")
        except EOFError:
            pass
        sys.exit(1)
