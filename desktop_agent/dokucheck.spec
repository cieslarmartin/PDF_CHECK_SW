# -*- mode: python ; coding: utf-8 -*-
# DokuCheck PRO – PyInstaller spec (onedir, windowed, pro digitální certifikaci)
# Spouštění: pyinstaller dokucheck.spec (ze složky desktop_agent)

block_cipher = None

# Datové soubory: logo (ikona v UI) a výchozí config pro první spuštění
# Při běhu exe jsou dostupné v sys._MEIPASS (onedir: vedle exe ve složce)
added_files = [
    ('logo', 'logo'),
    ('config.bez_klice.yaml', '.'),
]

icon_file = 'app_icon.ico'
import os
if not os.path.isfile(icon_file):
    icon_file = os.path.join('logo', 'logo.ico')
if not os.path.isfile(icon_file):
    icon_file = None

a = Analysis(
    ['pdf_check_agent_main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'customtkinter',
        'PIL',
        'PIL._tkinter_finder',
        'requests',
        'yaml',
        'tkinterdnd2',
        'license',
        'machine_id',
        'pdf_checker',
        'ui_2026_v3_enterprise',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DokuCheckPRO',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DokuCheckPRO',
)
