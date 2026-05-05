from __future__ import annotations

import argparse
import datetime as dt
import html
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from testovaci_engine import pdf_engine, pdf_engine_web


FIXTURE_ROOT = ROOT / "testovaci_engine" / "zdrojove PDF_testovaci"
REPORT_ROOT = ROOT / "testovaci_engine" / "reports"
SNAPSHOT_ROOT = REPORT_ROOT / "snapshots"


def load_legacy_web_module():
    web_file = ROOT / "web_app" / "pdf_check_web_main.py"
    web_dir = str(web_file.parent)
    if web_dir not in sys.path:
        sys.path.insert(0, web_dir)
    spec = importlib.util.spec_from_file_location("legacy_web_main", web_file)
    if spec is None or spec.loader is None:
        raise RuntimeError("Nelze nacist legacy web module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def list_pdf_files(base: Path) -> List[Path]:
    return sorted([p for p in base.rglob("*.pdf") if p.is_file()])


def normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in sorted(value.items(), key=lambda item: item[0])}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value


def flatten(prefix: str, value: Any, out: Dict[str, Any]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            flatten(f"{prefix}.{k}" if prefix else k, v, out)
        return
    if isinstance(value, list):
        for i, v in enumerate(value):
            flatten(f"{prefix}[{i}]", v, out)
        return
    out[prefix] = value


def diff_three(
    a: Dict[str, Any], b: Dict[str, Any], c: Dict[str, Any], ignore_fields: set[str] | None = None
) -> List[Dict[str, Any]]:
    fa: Dict[str, Any] = {}
    fb: Dict[str, Any] = {}
    fc: Dict[str, Any] = {}
    flatten("", normalize(a), fa)
    flatten("", normalize(b), fb)
    flatten("", normalize(c), fc)

    keys = sorted(set(fa.keys()) | set(fb.keys()) | set(fc.keys()))
    diffs: List[Dict[str, Any]] = []
    ignore_fields = ignore_fields or set()
    for key in keys:
        if key in ignore_fields:
            continue
        va = fa.get(key, "<missing>")
        vb = fb.get(key, "<missing>")
        vc = fc.get(key, "<missing>")
        if not (va == vb == vc):
            diffs.append({"field": key, "web_legacy": va, "agent_legacy": vb, "unified_new": vc})
    return diffs


def sanitize_filename(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(path))


def parse_pdfa_part(exact_version: str) -> Any:
    m = re.search(r"PDF/A-(\d)", exact_version or "")
    return int(m.group(1)) if m else None


def convert_agent_wrapped_to_flat(wrapped: Dict[str, Any], content: bytes) -> Dict[str, Any]:
    if not wrapped.get("success"):
        return {"error": wrapped.get("error", "unknown"), "name": wrapped.get("file_name", "unknown")}

    details = pdf_engine.get_pdfa_details(content)
    results = wrapped.get("results", {})
    pdf_format = results.get("pdf_format", {})
    signatures = results.get("signatures", [])
    signature_objs = [s for s in signatures if s.get("type") == "SIGNATURE"]

    if signature_objs:
        sig = "OK" if all(s.get("signer", "—") != "—" and s.get("ckait_number", "—") != "—" for s in signature_objs) else "PARTIAL"
    else:
        sig = "PARTIAL" if signatures else "FAIL"

    if any(s.get("timestamp_valid") for s in signatures):
        tsa = "TSA"
    elif any((s.get("date") not in ("—", None, "")) for s in signatures):
        tsa = "LOCAL"
    else:
        tsa = "NONE"

    signer = ", ".join(dict.fromkeys([s.get("signer", "—") for s in signature_objs if s.get("signer", "—") != "—"])) or "—"
    ckait = ", ".join(dict.fromkeys([s.get("ckait_number", "—") for s in signature_objs if s.get("ckait_number", "—") != "—"])) or "—"

    out_signatures = []
    for i, s in enumerate(signatures, 1):
        sig_type = s.get("type", "SIGNATURE")
        out_signatures.append(
            {
                "index": s.get("index", i),
                "type": sig_type,
                "valid": s.get("valid", False),
                "signature_type": s.get("signature_type"),
                "signer": s.get("signer", "—"),
                "ckait": s.get("ckait_number", "—"),
                "date": s.get("date", "—"),
                "tsa": "TSA" if s.get("timestamp_valid") else ("LOCAL" if s.get("date") not in (None, "", "—") else "NONE"),
                "tsa_issuer": s.get("tsa_issuer", "—"),
                "timestamp_valid": s.get("timestamp_valid", False),
                "certificate_valid": s.get("certificate_valid", False),
                "tsa_qualified": s.get("tsa_qualified", False),
                "name": s.get("name", s.get("signer", "—")),
            }
        )

    return {
        "name": wrapped.get("file_name", "unknown"),
        "pdfaVersion": parse_pdfa_part(pdf_format.get("exact_version", "")),
        "pdfaStatus": "OK" if pdf_format.get("is_pdf_a3") else "FAIL",
        "pdfVersion": details.get("pdf_version"),
        "pdfaConformance": details.get("pdfa_conformance"),
        "pdfaLevel": details.get("pdfa_level"),
        "sig": sig,
        "signer": signer,
        "ckait": ckait,
        "tsa": tsa,
        "sig_count": len(signatures),
        "signatures": out_signatures,
        "docmdp_level": results.get("docmdp_level"),
        "issr_compatible": results.get("issr_compatible", True),
    }


def render_html(rows: List[Dict[str, Any]], generated: str, output_file: Path) -> None:
    total = len(rows)
    same = sum(1 for r in rows if not r["diff"])
    diff = total - same
    html_rows = []
    for row in rows:
        css = "ok" if not row["diff"] else "diff"
        diff_list = "".join(
            f"<tr><td>{html.escape(d['field'])}</td>"
            f"<td>{html.escape(str(d['web_legacy']))}</td>"
            f"<td>{html.escape(str(d['agent_legacy']))}</td>"
            f"<td>{html.escape(str(d['unified_new']))}</td></tr>"
            for d in row["diff"][:80]
        )
        if not diff_list:
            diff_list = "<tr><td colspan='4'>Bez rozdilu</td></tr>"
        html_rows.append(
            f"<tr class='{css}'><td>{html.escape(row['file'])}</td><td>{len(row['diff'])}</td>"
            f"<td>{'OK' if not row['diff'] else 'DIFF'}</td></tr>"
            f"<tr><td colspan='3'><details><summary>Detaily</summary>"
            f"<table><thead><tr><th>Pole</th><th>Web legacy</th><th>Agent legacy</th><th>Unified</th></tr></thead>"
            f"<tbody>{diff_list}</tbody></table></details></td></tr>"
        )

    page = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Engine Compare Report</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:24px}}
table{{border-collapse:collapse;width:100%;margin:12px 0}}
th,td{{border:1px solid #ddd;padding:6px;font-size:13px;vertical-align:top}}
th{{background:#f1f5f9}}
.ok{{background:#ecfdf5}}
.diff{{background:#fef2f2}}
</style></head><body>
<h2>Srovnani 3 enginu</h2>
<p>Generovano: {html.escape(generated)} | Souboru: {total} | Shoda: {same} | Rozdily: {diff}</p>
<table><thead><tr><th>Soubor</th><th>Pocet rozdilu</th><th>Stav</th></tr></thead>
<tbody>{''.join(html_rows)}</tbody></table>
</body></html>"""
    output_file.write_text(page, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Volitelny limit poctu souboru")
    args = parser.parse_args()

    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)

    files = list_pdf_files(FIXTURE_ROOT)
    if args.limit and args.limit > 0:
        files = files[: args.limit]
    if not files:
        print(f"Nenalezeny PDF soubory v {FIXTURE_ROOT}")
        return 2

    legacy_web = load_legacy_web_module()
    rows: List[Dict[str, Any]] = []

    for idx, pdf_path in enumerate(files, 1):
        rel = pdf_path.relative_to(FIXTURE_ROOT)
        content = pdf_path.read_bytes()

        web_legacy = legacy_web.analyze_pdf_from_content(content)
        legacy_web._enrich_signatures_tsa_qualified(web_legacy)
        web_legacy["name"] = pdf_path.name

        agent_wrapped = pdf_engine.analyze_pdf_file(str(pdf_path))
        agent_flat = convert_agent_wrapped_to_flat(agent_wrapped, content)

        unified_web = pdf_engine_web.analyze_upload(content, filename=pdf_path.name)
        unified_agent_wrapped = pdf_engine.analyze_pdf_file(str(pdf_path))
        unified_agent_flat = convert_agent_wrapped_to_flat(unified_agent_wrapped, content)
        # Interni kontrola unified cesty: upload vs file
        unified_internal_diff = diff_three(
            unified_web, unified_agent_flat, unified_web, ignore_fields={"name"}
        )

        diffs = diff_three(web_legacy, agent_flat, unified_web)
        if unified_internal_diff:
            diffs.append(
                {
                    "field": "__unified_internal_path_diff__",
                    "web_legacy": f"{len(unified_internal_diff)} rozdilu",
                    "agent_legacy": "n/a",
                    "unified_new": "upload!=file",
                }
            )

        rows.append({"file": str(rel), "diff": diffs})

        snap_name = sanitize_filename(rel) + ".json"
        (SNAPSHOT_ROOT / snap_name).write_text(
            json.dumps(
                {
                    "file": str(rel),
                    "web_legacy": web_legacy,
                    "agent_legacy": agent_flat,
                    "unified_new": unified_web,
                    "diff_count": len(diffs),
                    "diff": diffs,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[{idx}/{len(files)}] {rel} -> {'OK' if not diffs else f'DIFF({len(diffs)})'}")

    generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out_html = REPORT_ROOT / f"compare_{dt.datetime.now().strftime('%Y-%m-%d_%H%M')}.html"
    render_html(rows, generated, out_html)

    diffs_total = sum(1 for r in rows if r["diff"])
    print("")
    print(f"Hotovo. Souboru: {len(rows)} | Se rozdilem: {diffs_total}")
    print(f"HTML report: {out_html}")
    return 1 if diffs_total else 0


if __name__ == "__main__":
    raise SystemExit(main())
