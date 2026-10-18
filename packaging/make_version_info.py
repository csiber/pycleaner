"""Windows-exe verzióinformáció (Fájl tulajdonságai → Részletek) generálása a csomag verziójából."""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
version = re.search(r'__version__ = "([^"]+)"', (ROOT / "pycleaner" / "__init__.py").read_text()).group(1)
nums = tuple(int(x) for x in re.findall(r"\d+", version)[:3]) + (0,)

TEMPLATE = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040E04B0', [
      StringStruct('CompanyName', 'Polyák Csaba'),
      StringStruct('FileDescription', 'PyCleaner rendszertisztító'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'PyCleaner'),
      StringStruct('LegalCopyright', 'MIT licenc — github.com/csiber/pycleaner'),
      StringStruct('OriginalFilename', 'PyCleaner.exe'),
      StringStruct('ProductName', 'PyCleaner'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [0x040E, 1200])])
  ]
)
"""
(ROOT / "packaging" / "version_info.txt").write_text(TEMPLATE, encoding="utf-8")
print(version if "--print" in sys.argv else f"version_info.txt kész ({version})")
