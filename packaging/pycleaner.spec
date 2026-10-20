# -*- mode: python ; coding: utf-8 -*-
# PyInstaller-spec. Futtatás a repó gyökeréből:
#   pyinstaller packaging/pycleaner.spec --noconfirm              -> dist/PyCleaner/ (telepítőhöz)
#   set PYC_ONEFILE=1 && pyinstaller packaging/pycleaner.spec     -> dist/PyCleaner-portable.exe
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ONEFILE = os.environ.get("PYC_ONEFILE") == "1"
VERSION_FILE = os.path.join(SPECPATH, "version_info.txt")

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "pycleaner", "templates"), "pycleaner/templates"),
           (os.path.join(ROOT, "pycleaner", "static"), "pycleaner/static")],
    hiddenimports=["winreg", "send2trash", "webview.platforms.edgechromium", "webview.platforms.winforms",
                   "pystray._win32", "PIL.Image", "PIL.PngImagePlugin"],
    excludes=["tkinter", "matplotlib", "numpy", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

common = dict(
    name="PyCleaner-portable" if ONEFILE else "PyCleaner",
    debug=False,
    strip=False,
    upx=False,            # az UPX-tömörítés gyakori víruskereső-téves riasztást okoz
    console=False,        # natív ablakos alkalmazás; naplók: %LOCALAPPDATA%\PyCleaner\pycleaner.log
    icon=os.path.join(ROOT, "pycleaner", "static", "favicon.ico"),
    version=VERSION_FILE if os.path.exists(VERSION_FILE) else None,
)

if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], runtime_tmpdir=None, **common)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **common)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="PyCleaner")
