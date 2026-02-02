# create_deploy_zip.py
# Zabale web_app do ZIPu s top-level složkou "web_app" pro PythonAnywhere.
# Po rozbalení v /home/username/ vznikne /home/username/web_app/ (stejný název jako na disku).
# Spusťte z kořene PDF_CHECK_SW:  python create_deploy_zip.py
# Výstup: web_app_deploy.zip

import zipfile
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB_APP = ROOT / "web_app"
OUT_ZIP = ROOT / "web_app_deploy.zip"
TOP_LEVEL = "web_app"  # na PA po unzip: /home/username/web_app/ (stejný název jako na disku)

EXCLUDE_DIRS = {"__pycache__", ".git", ".venv", "zaloha_pred_filtry"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}

def main():
    if not WEB_APP.is_dir():
        print(f"CHYBA: Složka {WEB_APP} neexistuje.")
        return
    count = 0
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(WEB_APP, topdown=True):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            root_path = Path(root)
            for name in files:
                if Path(name).suffix in EXCLUDE_SUFFIXES:
                    continue
                full = root_path / name
                try:
                    rel = full.relative_to(WEB_APP)
                except ValueError:
                    continue
                arcname = f"{TOP_LEVEL}/{rel.as_posix()}"
                zf.write(full, arcname)
                count += 1
    print(f"Hotovo: {count} souborů -> {OUT_ZIP}")
    print(f"Rozbal na PA v /home/TVOJE_JMENO/ -> vznikne {TOP_LEVEL}/")

if __name__ == "__main__":
    main()
