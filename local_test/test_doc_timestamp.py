# -*- coding: utf-8 -*-
"""Test detekce samostatného časového razítka (DocTimeStamp) vs. podpisu s vloženým TSA.
Spuštění z kořene projektu: python local_test/test_doc_timestamp.py
"""
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

from desktop_agent.pdf_checker import analyze_pdf_file

BAD_PDF = os.path.join(
    _root,
    "testovaci_engine",
    "zdrojove PDF_testovaci",
    "blatak",
    "04Z_01.1.60-07 Elektroinstalace-4.NP.pdf",
)
BAD_PDF_FALLBACK = r"c:\CURSOR_SOUBORY\Claude\testovaci PDF\blatak jen casove razitko\04Z_01.1.60-07 Elektroinstalace-4.NP.pdf"
GOOD_PDF = r"v:\CHVAT\04Z_01.1.60-07 Elektroinstalace-4.NP_spravny.pdf"


def _resolve_bad_pdf():
    if os.path.isfile(BAD_PDF):
        return BAD_PDF
    if os.path.isfile(BAD_PDF_FALLBACK):
        return BAD_PDF_FALLBACK
    return None


def _assert_bad_pdf(path):
    r = analyze_pdf_file(path)
    assert r.get("success"), r.get("error")
    results = r["results"]
    sigs = results["signatures"]
    sig_objs = [s for s in sigs if s.get("type") == "SIGNATURE"]
    ts_objs = [s for s in sigs if s.get("type") == "DOCUMENT_TIMESTAMP"]
    assert len(sig_objs) == 1, f"očekáván 1 podpis, máme {len(sig_objs)}"
    assert len(ts_objs) == 1, f"očekáváno 1 razítko dokumentu, máme {len(ts_objs)}"
    assert sig_objs[0].get("signer", "—") != "—", "podpis bez jména"
    assert sig_objs[0].get("ckait_number", "—") != "—", "podpis bez ČKAIT"
    assert not sig_objs[0].get("timestamp_valid"), "podpis nesmí mít vložené TSA"
    assert ts_objs[0].get("timestamp_valid"), "razítko dokumentu musí být validní"
    assert ts_objs[0].get("tsa_issuer", "—") != "—", "razítko bez TSA issuer"
    assert results.get("orphan_document_timestamp") is True
    warnings = results.get("warnings") or []
    assert any("vloženo do podpisu" in w for w in warnings), warnings
    print("OK chybný PDF:", os.path.basename(path))


def _assert_good_pdf(path):
    if not os.path.isfile(path):
        print("SKIP správný PDF – soubor není dostupný:", path)
        return
    r = analyze_pdf_file(path)
    assert r.get("success"), r.get("error")
    results = r["results"]
    sigs = results["signatures"]
    sig_objs = [s for s in sigs if s.get("type") == "SIGNATURE"]
    ts_objs = [s for s in sigs if s.get("type") == "DOCUMENT_TIMESTAMP"]
    assert len(sig_objs) == 1, f"očekáván 1 podpis, máme {len(sig_objs)}"
    assert len(ts_objs) == 0, f"nesmí být samostatné razítko, máme {len(ts_objs)}"
    assert sig_objs[0].get("timestamp_valid"), "podpis musí mít vložené TSA"
    assert not results.get("orphan_document_timestamp"), "nesmí být orphan warning"
    print("OK správný PDF:", os.path.basename(path))


def main():
    bad = _resolve_bad_pdf()
    if not bad:
        print("CHYBA: chybí testovací PDF (zkopírujte do testovaci_engine/zdrojove PDF_testovaci/blatak/)")
        sys.exit(1)
    _assert_bad_pdf(bad)
    _assert_good_pdf(GOOD_PDF)
    print("\nVšechny testy prošly.")


if __name__ == "__main__":
    main()
