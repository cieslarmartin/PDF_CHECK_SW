# -*- coding: utf-8 -*-
"""
Sestavení MSIX balíčku pro Microsoft Store (DokuCheck).
Spouštění: python store/build_msix.py [--skip-build]
(z desktop_agent nebo z kořene store/)

Výstup: desktop_agent/store/output/DokuCheck_{build}.msix
Nepoužívá Inno Setup ani install/ – .exe distribuce zůstává oddělená.
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

STORE_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR = os.path.dirname(STORE_DIR)
MSIX_DIR = os.path.join(STORE_DIR, "msix")
MANIFEST_TEMPLATE = os.path.join(MSIX_DIR, "AppxManifest.xml")
ASSETS_DIR = os.path.join(MSIX_DIR, "Assets")
DIST_APP = os.path.join(AGENT_DIR, "dist", "DokuCheckPRO")
OUTPUT_DIR = os.path.join(STORE_DIR, "output")
STAGING_DIR = os.path.join(STORE_DIR, "build", "staging")

MAKEAPPX_GLOB = r"C:\Program Files (x86)\Windows Kits\10\bin\*\x64\makeappx.exe"


def detect_versions():
    """Vrátí (build_version, msix_version) např. ('53', '26.2.8.0')."""
    version_py = os.path.join(AGENT_DIR, "version.py")
    if not os.path.isfile(version_py):
        raise SystemExit("CHYBA: Chybí desktop_agent/version.py")
    text = open(version_py, encoding="utf-8").read()
    m_build = re.search(r'BUILD_VERSION\s*=\s*["\']([^"\']+)["\']', text)
    m_agent = re.search(r'AGENT_VERSION\s*=\s*["\']([^"\']+)["\']', text)
    build = (m_build.group(1) if m_build else "0").strip()
    agent = (m_agent.group(1) if m_agent else "0.0.0").strip().lstrip("vVwW")
    parts = []
    for p in agent.split("."):
        try:
            parts.append(str(int(p)))
        except ValueError:
            parts.append("0")
    while len(parts) < 3:
        parts.append("0")
    msix_ver = ".".join(parts[:3]) + ".0"
    return build, msix_ver


def find_makeappx():
    paths = sorted(glob.glob(MAKEAPPX_GLOB), reverse=True)
    for p in paths:
        if os.path.isfile(p):
            return p
    raise SystemExit(
        "CHYBA: makeappx.exe nenalezen.\n"
        "  Nainstalujte Windows 10/11 SDK (Windows SDK for Desktop C++).\n"
        "  Očekávaná cesta: " + MAKEAPPX_GLOB
    )


def ensure_assets():
    required = [
        "Square44x44Logo.png",
        "Square150x150Logo.png",
        "StoreLogo.png",
    ]
    missing = [n for n in required if not os.path.isfile(os.path.join(ASSETS_DIR, n))]
    if not missing:
        return
    gen = os.path.join(MSIX_DIR, "generate_assets.py")
    print("Generuji chybějící ikony Assets/...")
    subprocess.run([sys.executable, gen], cwd=MSIX_DIR, check=True)


def run_pyinstaller():
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "dokucheck.spec", "--noconfirm"],
        cwd=AGENT_DIR,
        check=True,
    )
    exe = os.path.join(DIST_APP, "DokuCheckPRO.exe")
    if not os.path.isfile(exe):
        raise SystemExit(f"CHYBA: Po PyInstalleru chybí {exe}")


def build_staging(msix_version):
    if os.path.isdir(STAGING_DIR):
        shutil.rmtree(STAGING_DIR)
    os.makedirs(STAGING_DIR, exist_ok=True)

    manifest_src = open(MANIFEST_TEMPLATE, encoding="utf-8").read()
    manifest_src = manifest_src.replace("__MSIX_VERSION__", msix_version)
    with open(os.path.join(STAGING_DIR, "AppxManifest.xml"), "w", encoding="utf-8") as f:
        f.write(manifest_src)

    shutil.copytree(ASSETS_DIR, os.path.join(STAGING_DIR, "Assets"))
    shutil.copytree(DIST_APP, STAGING_DIR, dirs_exist_ok=True)


def pack_msix(output_path):
    makeappx = find_makeappx()
    if os.path.isfile(output_path):
        os.remove(output_path)
    subprocess.run(
        [makeappx, "pack", "/d", STAGING_DIR, "/p", output_path, "/o"],
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(description="Sestavení MSIX balíčku DokuCheck pro Microsoft Store")
    parser.add_argument("--skip-build", action="store_true", help="Nepouštět PyInstaller (použít existující dist/)")
    args = parser.parse_args()

    build, msix_version = detect_versions()
    print(f"Build: {build}  |  MSIX verze: {msix_version}\n")

    ensure_assets()
    if not args.skip_build:
        print("Spouštím PyInstaller...")
        run_pyinstaller()
    elif not os.path.isfile(os.path.join(DIST_APP, "DokuCheckPRO.exe")):
        raise SystemExit(f"CHYBA: --skip-build ale chybí {DIST_APP}")

    print("Připravuji staging složku...")
    build_staging(msix_version)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_name = f"DokuCheck_{build}.msix"
    output_path = os.path.join(OUTPUT_DIR, out_name)
    print(f"Balím MSIX: {output_path}")
    pack_msix(output_path)

    print("\nHotovo.")
    print(f"  Soubor: {output_path}")
    print(f"  Test:   Add-AppxPackage -Path \"{output_path}\"")
    print("  Partner Center: Start submission -> Packages -> nahrajte tento soubor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
