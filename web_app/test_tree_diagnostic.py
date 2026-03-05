#!/usr/bin/env python
# Jednorázový diagnostický test: proč se nezobrazuje stromová struktura výsledků?
# Spuštění: python test_tree_diagnostic.py

import sqlite3
import os
import sys

OUTPUT_FILE = "test_tree_diagnostic_result.txt"

def main():
    lines = []
    def log(s=""):
        lines.append(s)
        print(s)

    db_path = os.path.join(os.path.dirname(__file__), "pdfcheck_results.db")
    if not os.path.isfile(db_path):
        log("CHYBA: Databaze nenalezena: " + db_path)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return 1

    log("=== DIAGNOSTIKA STROMOVE STRUKTURY VYSLEDKU ===")
    log("Databaze: " + db_path)
    log("")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Existuje tabulka check_results a sloupec folder_path?
    cur.execute("PRAGMA table_info(check_results)")
    cols = [row[1] for row in cur.fetchall()]
    if "folder_path" not in cols:
        log("CHYBA: Tabulka check_results nema sloupec folder_path. Sloupce: " + ", ".join(cols))
        conn.close()
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return 1
    log("OK: Sloupec folder_path existuje.")
    log("")

    # Posledni zaznamy
    cur.execute("""
        SELECT batch_id, file_name, folder_path, created_at
        FROM check_results
        ORDER BY created_at DESC
        LIMIT 20
    """)
    rows = cur.fetchall()
    log("Poslednich 20 zaznamu (batch_id | file_name | folder_path | created_at):")
    log("-" * 80)
    for row in rows:
        r = dict(row)
        fp = r.get("folder_path")
        fp_str = repr(fp) if fp is not None else "NULL"
        log("  {} | {} | {} | {}".format(
            (r.get("batch_id") or "")[:20],
            (r.get("file_name") or "")[:35],
            fp_str,
            (r.get("created_at") or "")[:19]
        ))
    log("")

    # Statistiky folder_path
    cur.execute("SELECT COUNT(*) AS c FROM check_results")
    total = cur.fetchone()[0]
    cur.execute("""
        SELECT COUNT(*) AS c FROM check_results
        WHERE folder_path IS NULL OR folder_path = '' OR folder_path = '.'
    """)
    flat_count = cur.fetchone()[0]
    cur.execute("""
        SELECT COUNT(*) AS c FROM check_results
        WHERE folder_path IS NOT NULL AND folder_path != '' AND folder_path != '.'
    """)
    tree_count = cur.fetchone()[0]

    log("Statistiky folder_path:")
    log("  Celkem zaznamu: " + str(total))
    log("  S folder_path NULL / '' / '.': " + str(flat_count) + " (strom SE NEZOBRAZI)")
    log("  S folder_path vyplnenym (napr. slozka/cesta): " + str(tree_count) + " (strom SE ZOBRAZI)")
    log("")

    if total > 0:
        if tree_count == 0:
            log("ZAVER: Vsechny zaznamy maji prazdny nebo '.' folder_path.")
            log("       Frontend zobrazuje strom jen kdyz aspon jeden soubor ma cestu s podslozkou.")
            log("       Mozna pricina: agent neposlal 'folder' pri uploadu, nebo vsechny kontroly byly single-file / plocha slozka.")
        else:
            log("ZAVER: Nektere zaznamy maji folder_path vyplneny - strom by se mel zobrazit u techto davek.")
            log("       Pokud strom nevidite, mozna jde o chybu ve frontendu (napr. spatny klic nebo CSS).")

    conn.close()

    # --- Simulace frontend logiky (buildFolderTree + hasSubfolders) ---
    log("")
    log("=== SIMULACE FRONTENDU (kdy se strom zobrazi?) ===")
    def build_folder_tree(files):
        tree = {"name": "__root", "folders": {}, "files": []}
        for f in files:
            path = (f.get("path") or "").replace("\\\\", "/")
            parts = path.split("/")
            if len(parts) <= 1:
                tree["files"].append(f)
            else:
                current = tree
                for i in range(len(parts) - 1):
                    name = parts[i]
                    if name not in current["folders"]:
                        current["folders"][name] = {"name": name, "folders": {}, "files": []}
                    current = current["folders"][name]
                current["files"].append(f)
        return tree

    # Priklad: vsechny soubory v rootu (jako kdyz agent posle folder_path = '.' nebo '')
    sample_flat = [
        {"name": "a.pdf", "path": "a.pdf"},
        {"name": "b.pdf", "path": "b.pdf"},
    ]
    t_flat = build_folder_tree(sample_flat)
    has_sub_flat = len(t_flat["folders"]) > 0
    log("  Data: vsechny soubory v rootu (path = jen file_name):")
    log("    hasSubfolders = " + str(has_sub_flat) + " -> strom SE NEZOBRAZI (aktualni kod)")

    # Priklad: soubory v podslozkach (jako kdyz agent posle folder_path = 'IO-01/A')
    sample_tree = [
        {"name": "soubor.pdf", "path": "IO-01/A/soubor.pdf"},
        {"name": "druhy.pdf", "path": "IO-01/A/druhy.pdf"},
    ]
    t_tree = build_folder_tree(sample_tree)
    has_sub_tree = len(t_tree["folders"]) > 0
    log("  Data: soubory v podslozkach (path = folder_path + '/' + file_name):")
    log("    hasSubfolders = " + str(has_sub_tree) + " -> strom SE ZOBRAZI")

    log("")
    log("DUSLEDEK: Strom se zobrazi jen kdyz aspon jeden soubor ma folder_path s cestou (ne '.').")
    log("          Pokud agent posila u vsech vysledku folder_path = '.' nebo prazdne, strom nikdy nebude.")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log("")
    log("Vysledek zapsan do: " + OUTPUT_FILE)
    return 0

if __name__ == "__main__":
    sys.exit(main())
