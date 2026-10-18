# Fejlesztés

## Forrásból futtatás

```bash
git clone https://github.com/csiber/pycleaner.git && cd pycleaner
python -m venv .venv && .venv\Scripts\activate     # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python main.py               # natív ablak (pywebview)
python main.py --browser     # alapértelmezett böngészőben
python main.py --no-open --port 5000   # csak a szerver, fejlesztéshez
python -m pytest -q
```

Python 3.10+. A `PYCLEANER_DATA` környezeti változóval külön adatmappa adható meg (a tesztek is így izolálnak).

## Felépítés

```
main.py                  belépési pont (forrás és PyInstaller)
pycleaner/
  launcher.py            szabad port, token, Flask háttérszálon, pywebview-ablak vagy böngésző
  server.py              Flask-alkalmazás: felület + /api, token/Host-védelem, CSP
  cleaner.py             kategóriák és célmappák OS-enként, beolvasás, tisztítás, ZIP-mentés
  fsutil.py              biztonságos bejárás és törlés (candidates/measure/clean_dir), Lomtár
  registry.py            registry-keresés és -javítás .reg mentéssel
  tweaks.py              Appx-csomagok, OneDrive
  winapi.py              ctypes: admin-ellenőrzés, UAC-újraindítás, Lomtár, visszaállítási pont
  analyzer.py            mappaméretek, nagy fájlok
  duplicates.py          duplikátumkeresés (méret → 64 KB → BLAKE2b)
  monitor.py             psutil-mintavétel (SSE)
  scheduler.py           háttérütemező
  store.py               JSON-tárolás (atomikus írás), profilok, jelszó-hash
  updates.py             GitHub Releases ellenőrzés
  report.py              HTML-riport
  templates/index.html   a felület váza (a token a <meta> tagben)
  static/                app.js, app.css, ikonok (Lucide), logó
packaging/               PyInstaller-spec, Inno Setup, build.ps1, verzióinformáció
tests/                   pytest
```

A felület keretrendszer nélküli JavaScript; minden dinamikus szöveg `esc()`-en megy át, inline szkript nincs (a CSP ezt meg is követeli).

## Új tisztítási kategória

1. `cleaner._targets()` — add hozzá a mappákat `Target(...)`-ként (kor, kiterjesztés, előtag szabályokkal).
2. `cleaner.categories()` — `Category(...)` címkével, leírással, ikonnal (`static/icons.svg` `i-<név>` szimbólumai), `default`, `admin`, `caution` mezőkkel.
3. Vedd fel a `CATEGORY_IDS` halmazba és a `report.LABELS`-be.
4. Írj tesztet: a célmappa ne legyen védett, és ne essen személyes adatra.

## Windows-build

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

Eredmény: `dist\PyCleaner\` (mappás), `dist\PyCleaner-portable.exe`, és ha telepítve van az Inno Setup 6, `dist\PyCleaner-<verzió>-Setup.exe`.

## Kiadás

1. Emeld a verziót a `pycleaner/__init__.py`-ban.
2. Írd meg a `CHANGELOG.md` új szakaszát (`## [x.y.z] — dátum`) — ez lesz a kiadás leírása.
3. `git tag vX.Y.Z && git push origin vX.Y.Z`

A [Windows-kiadás](https://github.com/csiber/pycleaner/actions/workflows/release.yml) workflow lefuttatja a teszteket, ellenőrzi, hogy a címke egyezik-e a verzióval, elkészíti és füstteszteli az exe-t, lefordítja a telepítőt, majd feltölti a fájlokat és az SHA256-összegeket a GitHub Release-be.
