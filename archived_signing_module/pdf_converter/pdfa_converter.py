# pdfa_converter.py
# Převod PDF na PDF/A-3 formát
# Build 1.0 | © 2025 Ing. Martin Cieślar

import os
import sys
import subprocess
import shutil
import logging
from pathlib import Path
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)

# Cesty k Ghostscript - zkusíme najít automaticky
GHOSTSCRIPT_PATHS = [
    r"C:\Program Files\gs\gs10.02.1\bin\gswin64c.exe",
    r"C:\Program Files\gs\gs10.02.0\bin\gswin64c.exe",
    r"C:\Program Files\gs\gs10.01.2\bin\gswin64c.exe",
    r"C:\Program Files\gs\gs10.01.1\bin\gswin64c.exe",
    r"C:\Program Files\gs\gs10.00.0\bin\gswin64c.exe",
    r"C:\Program Files\gs\gs9.56.1\bin\gswin64c.exe",
    r"C:\Program Files\gs\gs9.55.0\bin\gswin64c.exe",
    r"C:\Program Files (x86)\gs\gs10.02.1\bin\gswin32c.exe",
    r"C:\Program Files (x86)\gs\gs9.56.1\bin\gswin32c.exe",
    "gswin64c",  # Pokud je v PATH
    "gswin32c",
    "gs",
]


def find_ghostscript() -> Optional[str]:
    """
    Najde cestu k Ghostscript.
    Hledá v:
    1. Distribuci aplikace (vedle exe) - pro standalone aplikaci
    2. Standardních cestách Windows
    3. PATH
    """
    # 1. Hledáme v distribuci aplikace (vedle exe) - pro PyInstaller
    if getattr(sys, 'frozen', False):
        # Aplikace je zabalená (PyInstaller)
        base_path = os.path.dirname(sys.executable)
        # Zkusíme najít gswin64c.exe nebo gswin32c.exe vedle exe
        for gs_name in ['gswin64c.exe', 'gswin32c.exe', 'gs.exe']:
            gs_path = os.path.join(base_path, gs_name)
            if os.path.isfile(gs_path):
                logger.info(f"Nalezen Ghostscript v distribuci: {gs_path}")
                return gs_path
    
    # 2. Standardní cesty Windows
    for path in GHOSTSCRIPT_PATHS:
        if os.path.isfile(path):
            return path
        # Zkusíme najít v PATH
        gs_path = shutil.which(path)
        if gs_path:
            return gs_path
    
    return None


def convert_to_pdfa(input_path: str, output_path: Optional[str] = None,
                    pdfa_version: str = "3", conformance: str = "B") -> Tuple[bool, str]:
    """
    Převede PDF na PDF/A formát pomocí Ghostscript.

    Args:
        input_path: Cesta ke vstupnímu PDF
        output_path: Cesta k výstupnímu PDF (pokud None, přidá _pdfa suffix)
        pdfa_version: Verze PDF/A (1, 2, nebo 3)
        conformance: Úroveň conformance (A nebo B)

    Returns:
        Tuple (success, message)
    """
    input_path = Path(input_path)

    if not input_path.exists():
        return False, f"Soubor neexistuje: {input_path}"

    if output_path is None:
        suffix = f"_pdfa{pdfa_version}{conformance.lower()}"
        output_path = input_path.parent / f"{input_path.stem}{suffix}{input_path.suffix}"
    else:
        output_path = Path(output_path)

    # Najdeme Ghostscript
    gs_path = find_ghostscript()
    if not gs_path:
        return False, "Ghostscript není nainstalován. Stáhněte z: https://ghostscript.com/releases/gsdnld.html"

    # Vytvoříme PDFA definition file
    pdfa_def = _create_pdfa_def(pdfa_version, conformance)

    try:
        # Ghostscript příkaz pro PDF/A konverzi
        cmd = [
            gs_path,
            "-dPDFA=" + pdfa_version,
            "-dBATCH",
            "-dNOPAUSE",
            "-dNOOUTERSAVE",
            "-dUseCIEColor",
            "-sProcessColorModel=DeviceRGB",
            "-sDEVICE=pdfwrite",
            "-dPDFACompatibilityPolicy=1",
            f"-sOutputFile={output_path}",
            "-dAutoRotatePages=/None",
            "-dCompatibilityLevel=1.7",
            pdfa_def,
            str(input_path)
        ]

        logger.info(f"Spouštím Ghostscript: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minut timeout
        )

        # Odstraníme dočasný soubor
        if os.path.exists(pdfa_def):
            os.remove(pdfa_def)

        if result.returncode == 0:
            # Ověříme že výstup existuje a má rozumnou velikost
            if output_path.exists() and output_path.stat().st_size > 0:
                return True, f"Převedeno na PDF/A-{pdfa_version}{conformance} → {output_path.name}"
            else:
                return False, "Ghostscript skončil bez chyby, ale výstupní soubor je prázdný"
        else:
            error_msg = result.stderr or result.stdout or "Neznámá chyba"
            logger.error(f"Ghostscript chyba: {error_msg}")
            return False, f"Chyba Ghostscript: {error_msg[:200]}"

    except subprocess.TimeoutExpired:
        return False, "Časový limit vypršel (5 minut)"
    except FileNotFoundError:
        return False, f"Ghostscript nenalezen: {gs_path}"
    except Exception as e:
        logger.exception(f"Chyba při konverzi na PDF/A: {e}")
        return False, f"Chyba: {str(e)}"


def _create_pdfa_def(version: str, conformance: str) -> str:
    """
    Vytvoří dočasný PDFA definition PostScript soubor.
    """
    import tempfile

    # PDF/A definice
    pdfa_def_content = f"""%!
% PDF/A-{version}{conformance} definition file

% Required for PDF/A
/ICCProfile (sRGB Color Space Profile.icm) def

% PDF/A version
[/Title (PDF/A-{version}{conformance} Document)
 /DOCINFO pdfmark

% Metadata
[ /Subtype /XML
  /Type /Metadata
  /ModDate (D:20250201120000)
  /CreationDate (D:20250201120000)
  /Creator (PDF DokuCheck Converter)
  /Producer (Ghostscript with PDF/A-{version}{conformance})
  /Title (Converted Document)
  /Author (PDF DokuCheck)
  /Keywords (PDF/A-{version}{conformance})
  /DOCINFO pdfmark
"""

    # Vytvoříme dočasný soubor
    fd, path = tempfile.mkstemp(suffix='.ps', prefix='pdfa_def_')
    with os.fdopen(fd, 'w') as f:
        f.write(pdfa_def_content)

    return path


def convert_to_pdfa_batch(input_files: List[str], output_dir: Optional[str] = None,
                          pdfa_version: str = "3", conformance: str = "B") -> List[Tuple[str, bool, str]]:
    """
    Dávkový převod více PDF souborů na PDF/A.

    Args:
        input_files: Seznam cest k PDF souborům
        output_dir: Výstupní složka
        pdfa_version: Verze PDF/A
        conformance: Úroveň conformance

    Returns:
        Seznam výsledků: [(filename, success, message), ...]
    """
    results = []

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    for input_path in input_files:
        input_path = Path(input_path)

        if output_dir:
            suffix = f"_pdfa{pdfa_version}{conformance.lower()}"
            output_path = output_dir / f"{input_path.stem}{suffix}{input_path.suffix}"
        else:
            output_path = None

        success, message = convert_to_pdfa(
            str(input_path),
            str(output_path) if output_path else None,
            pdfa_version,
            conformance
        )
        results.append((input_path.name, success, message))

    return results


def check_ghostscript() -> Tuple[bool, str]:
    """
    Zkontroluje dostupnost Ghostscript.

    Returns:
        Tuple (available, version_or_error)
    """
    gs_path = find_ghostscript()

    if not gs_path:
        return False, "Ghostscript není nainstalován"

    try:
        result = subprocess.run(
            [gs_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            version = result.stdout.strip()
            return True, f"Ghostscript {version}"
        else:
            return False, "Ghostscript nalezen, ale nefunguje správně"

    except Exception as e:
        return False, f"Chyba při kontrole Ghostscript: {e}"


# Test
if __name__ == "__main__":
    import sys

    # Kontrola Ghostscript
    available, info = check_ghostscript()
    print(f"Ghostscript: {'✓' if available else '✗'} {info}")

    if len(sys.argv) < 2:
        print("\nPoužití: python pdfa_converter.py <input.pdf> [output.pdf]")
        sys.exit(0 if available else 1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    success, message = convert_to_pdfa(input_file, output_file)
    print(f"{'✓' if success else '✗'} {message}")
