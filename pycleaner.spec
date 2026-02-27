# -*- mode: python ; coding: utf-8 -*-
# PyCleaner v3.0 — PyInstaller build spec
# Futtatás: pyinstaller pycleaner.spec

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Az összes Flask/Jinja2 adat összegyűjtése
datas = [
    ('templates',  'templates'),   # HTML sablonok
    ('static',     'static'),      # CSS, JS, képek, favicon
]

# Rejtett importok (Flask belső moduljai, amiket PyInstaller nem talál meg automatikusan)
hidden_imports = [
    'flask',
    'flask.templating',
    'jinja2',
    'jinja2.ext',
    'werkzeug',
    'werkzeug.serving',
    'werkzeug.routing',
    'werkzeug.middleware',
    'werkzeug.middleware.proxy_fix',
    'click',
    'psutil',
    'hashlib',
    'zipfile',
    'threading',
    'socket',
    'webbrowser',
    'winreg',       # Windows registry (csak Windows)
    'encodings',
    'encodings.utf_8',
    'encodings.ascii',
    'encodings.latin_1',
]

a = Analysis(
    ['main.py'],                   # Belépési pont
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',                 # Nem kell
        'matplotlib',
        'numpy',
        'scipy',
        'PIL',
        'IPython',
        'jupyter',
        'notebook',
        'test',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PyCleaner',              # Exe neve
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                      # UPX tömörítés (kisebb exe)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,                  # Console ablak látható (hasznos hibakereséshez)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='static\\favicon.ico',    # Exe ikon (Windows)
    version_file=None,
    onefile=True,                  # Egyetlen exe fájl (--onefile)
)
