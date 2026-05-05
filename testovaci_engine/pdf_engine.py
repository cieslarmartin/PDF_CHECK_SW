"""Sjednoceny PDF engine pro offline porovnani.

Faze 1: Pouziva aktualni desktop engine jako zdroj pravdy.
"""

from __future__ import annotations

import os
import re
import tempfile
from typing import Any, Dict

from desktop_agent import pdf_checker as legacy_engine
try:
    from desktop_agent.tsa_registry import is_tsa_issuer_qualified as _tsa_qualified
    legacy_engine.is_tsa_issuer_qualified = _tsa_qualified
except Exception:
    pass


# Re-export desktop API, aby byl testovaci modul kompatibilni.
check_pdfa_version = legacy_engine.check_pdfa_version
extract_signatures_via_reader = legacy_engine.extract_signatures_via_reader
extract_all_signatures = legacy_engine.extract_all_signatures
check_signature_data = legacy_engine.check_signature_data
check_timestamp = legacy_engine.check_timestamp
detect_docmdp_lock_via_reader = legacy_engine.detect_docmdp_lock_via_reader
detect_docmdp_lock = legacy_engine.detect_docmdp_lock
analyze_pdf = legacy_engine.analyze_pdf
analyze_pdf_file = legacy_engine.analyze_pdf_file
find_all_pdfs = legacy_engine.find_all_pdfs
analyze_multiple_pdfs = legacy_engine.analyze_multiple_pdfs
analyze_folder = legacy_engine.analyze_folder


def get_pdfa_details(content: bytes) -> Dict[str, Any]:
    """Vrati webova doplnkova pole: pdf_version, conformance, level."""
    pdf_version = ""
    conformance = ""
    try:
        pdf_header = re.search(rb"%PDF-(\d+\.\d+)", content[:100])
        if pdf_header:
            pdf_version = pdf_header.group(1).decode("ascii")
    except Exception:
        pass

    try:
        conf_match = re.search(
            rb"pdfaid:conformance=['\"]?([ABUYabuy])['\"]?", content, re.IGNORECASE
        )
        if conf_match:
            conformance = conf_match.group(1).decode("ascii").lower()
        if not conformance:
            for level in (b"PDF/A-3y", b"PDF/A-3u", b"PDF/A-3b", b"PDF/A-3a"):
                if level in content:
                    conformance = level.decode("ascii")[-1].lower()
                    break
    except Exception:
        pass

    part, _status = check_pdfa_version(content)
    pdfa_level = ""
    if part == 3 and conformance:
        pdfa_level = f"A-3{conformance}"
    elif part:
        pdfa_level = f"A-{part}"

    return {
        "pdf_version": pdf_version or None,
        "pdfa_conformance": conformance or None,
        "pdfa_level": pdfa_level or None,
    }


def analyze_from_bytes(content: bytes, filename: str = "upload.pdf") -> Dict[str, Any]:
    """Simulace web upload cesty: bytes -> temporary file -> analyze_pdf_file."""
    suffix = ".pdf"
    if filename and "." in filename:
        _, ext = os.path.splitext(filename)
        if ext:
            suffix = ext

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        result = analyze_pdf_file(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    if isinstance(result, dict) and result.get("success"):
        result["file_name"] = filename or result.get("file_name", "upload.pdf")
        if "results" in result and isinstance(result["results"], dict):
            info = result["results"].setdefault("file_info", {})
            info["filename"] = result["file_name"]
    return result
