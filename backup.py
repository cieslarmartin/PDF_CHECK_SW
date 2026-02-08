# backup.py – záloha projektu do ZIP (bez venv, .git, archive)
# Spusť z kořene projektu: python backup.py

import os
import zipfile
from datetime import datetime

# Složky a soubory, které se do zálohy nepřidávají
EXCLUDE = {'venv', '.git', 'archive'}


def main():
    project_root = os.path.abspath(os.path.dirname(__file__))
    archive_dir = os.path.join(project_root, 'archive')
    os.makedirs(archive_dir, exist_ok=True)

    today = datetime.now()
    zip_name = 'backup_{:04d}_{:02d}_{:02d}.zip'.format(today.year, today.month, today.day)
    zip_path = os.path.join(archive_dir, zip_name)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(project_root):
            # Neprojít do vyloučených složek (venv, .git, archive)
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE]

            rel_root = os.path.relpath(dirpath, project_root)
            # Nezařazovat do ZIPu nic ze složky archive (cíl zálohy)
            if rel_root == 'archive' or rel_root.startswith('archive' + os.sep):
                dirnames[:] = []
                continue

            for fname in filenames:
                filepath = os.path.join(dirpath, fname)
                arcname = os.path.join(rel_root, fname)
                zf.write(filepath, arcname)

    print('Záloha uložena:', os.path.normpath(zip_path))
    return zip_path


if __name__ == '__main__':
    main()
