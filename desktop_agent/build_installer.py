# -*- coding: utf-8 -*-
"""
Automatický build Windows instalátoru DokuCheck PRO.
Spouštění z kořene desktop_agent: python build_installer.py

1. Detekuje BUILD_VERSION / VERSION z ui.py (nebo pdf_check_agent_main.py).
2. Spustí PyInstaller (dokucheck.spec --noconfirm).
3. Vygeneruje .iss s verzí, spustí Inno Setup (ISCC).
4. Přejmenuje výstup na DokuCheckPRO_Setup_{verze}_{datum}.exe v install/.
5. Smaže build/ a dist/.
"""

import os
import re
import sys
import shutil
import subprocess
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INSTALL_DIR = os.path.join(SCRIPT_DIR, "install")
ISS_TEMPLATE = os.path.join(INSTALL_DIR, "installer_config.iss")
ISS_BUILD = os.path.join(INSTALL_DIR, "installer_config_build.iss")
BUILD_DIR = os.path.join(SCRIPT_DIR, "build")
DIST_DIR = os.path.join(SCRIPT_DIR, "dist")
DIST_APP = os.path.join(DIST_DIR, "DokuCheckPRO")

# Jediný zdroj pravdy: desktop_agent/version.py (BUILD_VERSION)
VERSION_SOURCES = [
    (os.path.join(SCRIPT_DIR, "version.py"), re.compile(r'BUILD_VERSION\s*=\s*["\']([^"\']+)["\']')),
    (os.path.join(SCRIPT_DIR, "ui.py"), re.compile(r'BUILD_VERSION\s*=\s*["\']([^"\']+)["\']')),
    (os.path.join(SCRIPT_DIR, "ui.py"), re.compile(r'VERSION\s*=\s*["\']([^"\']+)["\']')),
]

# Inno Setup 6: 32bit a 64bit standardní cesty
INNO_PATHS = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]


def detect_version():
    """Načte verzi z BUILD_VERSION nebo VERSION v ui.py / pdf_check_agent_main.py."""
    for filepath, pattern in VERSION_SOURCES:
        if not os.path.isfile(filepath):
            continue
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    raise SystemExit("CHYBA: Nepodařilo se najít BUILD_VERSION v desktop_agent/version.py.")


def find_iscc():
    """Vrátí cestu k ISCC.exe (PATH nebo standardní instalace)."""
    iscc = shutil.which("iscc")
    if iscc:
        return iscc
    for path in INNO_PATHS:
        if os.path.isfile(path):
            return path
    raise SystemExit(
        "CHYBA: Inno Setup 6 (ISCC) nenalezen.\n"
        "  Nainstalujte Inno Setup 6 nebo přidejte ISCC.exe do PATH.\n"
        "  Očekávané cesty: " + ", ".join(INNO_PATHS)
    )


def check_pyinstaller():
    """Ověří, že PyInstaller je nainstalovaný."""
    try:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            cwd=SCRIPT_DIR,
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise SystemExit(
            "CHYBA: PyInstaller není nainstalovaný nebo nefunguje.\n"
            "  Nainstalujte: pip install pyinstaller\n"
            "  (v aktivním venv nebo pro uživatele: pip install --user pyinstaller)"
        ) from e


def run_pyinstaller():
    """Spustí PyInstaller ze složky desktop_agent."""
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "dokucheck.spec", "--noconfirm"],
        cwd=SCRIPT_DIR,
        check=True,
    )
    exe_path = os.path.join(DIST_APP, "DokuCheckPRO.exe")
    if not os.path.isfile(exe_path):
        raise SystemExit(
            f"CHYBA: Po PyInstalleru chybí očekávaný soubor:\n  {exe_path}\n"
            "  Zkontrolujte výstup PyInstalleru výše."
        )
    print(f"  OK: {exe_path}")


def run_inno_setup(version):
    """Připraví .iss s verzí a spustí ISCC; pracovní adresář = install/."""
    with open(ISS_TEMPLATE, "r", encoding="utf-8") as f:
        content = f.read()
    # Nahradit #define MyAppVersion "..." za aktuální verzi
    content = re.sub(
        r'#define\s+MyAppVersion\s+"[^"]*"',
        f'#define MyAppVersion "{version}"',
        content,
        count=1,
    )
    with open(ISS_BUILD, "w", encoding="utf-8") as f:
        f.write(content)

    iscc = find_iscc()
    subprocess.run(
        [iscc, os.path.basename(ISS_BUILD)],
        cwd=INSTALL_DIR,
        check=True,
    )
    # Odstranit dočasný vygenerovaný .iss (volitelné, může zůstat pro debug)
    try:
        os.remove(ISS_BUILD)
    except OSError:
        pass


def finalize_installer(version):
    """Přejmenuje výstup na DokuCheckPRO_Setup_{verze}_{datum}.exe v install/."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    final_name = f"DokuCheckPRO_Setup_{version}_{date_str}.exe"
    final_path = os.path.join(INSTALL_DIR, final_name)
    # Inno vytvoří DokuCheckPRO_Setup_{version}.exe (bez data)
    base_name = f"DokuCheckPRO_Setup_{version}.exe"
    base_path = os.path.join(INSTALL_DIR, base_name)
    if not os.path.isfile(base_path):
        raise SystemExit(f"CHYBA: Po buildu chybí očekávaný soubor: {base_path}")
    if os.path.isfile(final_path):
        os.remove(final_path)
    shutil.move(base_path, final_path)
    print(f"Instalátor uložen: {final_path}")
    return final_path


def clean_build_dirs():
    """Smaže build/ a dist/ v desktop_agent."""
    for d in (BUILD_DIR, DIST_DIR):
        if os.path.isdir(d):
            shutil.rmtree(d)
            print(f"Smazáno: {d}")


def main():
    os.chdir(SCRIPT_DIR)
    print("=== Build instalátoru DokuCheck PRO ===\n")
    print("Kontrola závislostí…")
    check_pyinstaller()
    iscc_path = find_iscc()
    print(f"  PyInstaller: OK")
    print(f"  Inno Setup (ISCC): {iscc_path}\n")

    version = detect_version()
    print(f"Detekovaná verze: {version}\n")

    print("Krok 1/4: PyInstaller…")
    run_pyinstaller()

    print("Krok 2/4: Inno Setup…")
    run_inno_setup(version)

    print("Krok 3/4: Přejmenování a přesun do install/…")
    finalize_installer(version)

    print("Krok 4/4: Čištění build/ a dist/…")
    clean_build_dirs()

    print("Hotovo.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n--- CHYBA ---")
        import traceback
        traceback.print_exc()
        print("\nVýstup výše ukazuje, kde build selhal. Viz NAVOD_BUILD_INSTALATOR.md.")
        try:
            input("Stiskněte Enter pro ukončení…")
        except EOFError:
            pass
        sys.exit(1)
