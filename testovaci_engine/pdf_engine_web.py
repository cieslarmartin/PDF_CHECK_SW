"""Web adapter nad sjednocenym enginem.

Vraci co nejpodobnejsi strukturu jako legacy web analyzer.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List

from testovaci_engine import pdf_engine

try:
    from desktop_agent.tsa_registry import is_tsa_issuer_qualified
except Exception:
    def is_tsa_issuer_qualified(_: str) -> bool:
        return False


def _flatten_wrapped_result(wrapped: Dict[str, Any], details: Dict[str, Any]) -> Dict[str, Any]:
    results = wrapped.get("results", {}) if isinstance(wrapped, dict) else {}
    signatures = results.get("signatures", []) if isinstance(results, dict) else []
    pdf_format = results.get("pdf_format", {}) if isinstance(results, dict) else {}

    signer_values = [s.get("signer", "—") for s in signatures if s.get("type") == "SIGNATURE" and s.get("signer", "—") != "—"]
    ckait_values = [s.get("ckait_number", "—") for s in signatures if s.get("type") == "SIGNATURE" and s.get("ckait_number", "—") != "—"]
    signer_join = ", ".join(dict.fromkeys(signer_values)) if signer_values else "—"
    ckait_join = ", ".join(dict.fromkeys(ckait_values)) if ckait_values else "—"

    if any(s.get("timestamp_valid") for s in signatures):
        tsa = "TSA"
    elif any(s.get("date") not in (None, "—", "") for s in signatures):
        tsa = "LOCAL"
    else:
        tsa = "NONE"

    sig_types = [s.get("type") for s in signatures]
    signature_objs = [s for s in signatures if s.get("type") == "SIGNATURE"]
    if signature_objs:
        all_valid = all((s.get("signer", "—") != "—" and s.get("ckait_number", "—") != "—") for s in signature_objs)
        sig = "OK" if all_valid else "PARTIAL"
    else:
        sig = "PARTIAL" if sig_types else "FAIL"

    out_signatures: List[Dict[str, Any]] = []
    for idx, s in enumerate(signatures, 1):
        sig_type = s.get("type", "SIGNATURE")
        tsa_issuer = s.get("tsa_issuer", "—")
        out_signatures.append(
            {
                "index": s.get("index", idx),
                "type": sig_type,
                "valid": s.get("valid", False),
                "signature_type": s.get("signature_type"),
                "signer": s.get("signer", "—"),
                "ckait": s.get("ckait_number", "—"),
                "date": s.get("date", "—"),
                "tsa": "TSA" if s.get("timestamp_valid") else ("LOCAL" if s.get("date") not in (None, "—", "") else "NONE"),
                "tsa_issuer": tsa_issuer,
                "timestamp_valid": s.get("timestamp_valid", False),
                "certificate_valid": s.get("certificate_valid", False),
                "tsa_qualified": is_tsa_issuer_qualified(tsa_issuer) if tsa_issuer and tsa_issuer != "—" else False,
                "name": (
                    f"Časové razítko dokumentu ({tsa_issuer if tsa_issuer != '—' else '—'})"
                    if sig_type == "DOCUMENT_TIMESTAMP"
                    else s.get("signer", "—")
                ),
            }
        )

    exact_version = str(pdf_format.get("exact_version", ""))
    m = re.search(r"PDF/A-(\d)", exact_version)
    pdfa_version = int(m.group(1)) if m else None

    return {
        "name": wrapped.get("file_name", "upload.pdf"),
        "pdfaVersion": pdfa_version,
        "pdfaStatus": "OK" if pdf_format.get("is_pdf_a3") else "FAIL",
        "pdfVersion": details.get("pdf_version"),
        "pdfaConformance": details.get("pdfa_conformance"),
        "pdfaLevel": details.get("pdfa_level"),
        "sig": sig,
        "signer": signer_join,
        "ckait": ckait_join,
        "tsa": tsa,
        "sig_count": len(out_signatures),
        "signatures": out_signatures,
        "docmdp_level": results.get("docmdp_level"),
        "issr_compatible": results.get("issr_compatible", True),
    }


def analyze_upload(content: bytes, filename: str = "upload.pdf") -> Dict[str, Any]:
    wrapped = pdf_engine.analyze_from_bytes(content, filename=filename)
    details = pdf_engine.get_pdfa_details(content)
    return _flatten_wrapped_result(wrapped, details)


def analyze_file(filepath: str) -> Dict[str, Any]:
    wrapped = pdf_engine.analyze_pdf_file(filepath)
    with open(filepath, "rb") as f:
        content = f.read()
    details = pdf_engine.get_pdfa_details(content)
    out = _flatten_wrapped_result(wrapped, details)
    out["name"] = os.path.basename(filepath)
    return out
