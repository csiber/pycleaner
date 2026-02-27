# PyCleaner v3.0 — Rendszertisztító

## 🚀 Gyors indítás (Python)
```bash
pip install flask psutil
python app.py
# Böngésző: http://localhost:5000
```

---

## 📦 EXE készítése (Windows)

### Automatikus (ajánlott)
1. Másold a mappát Windows-ra
2. Dupla kattintás: **`build.bat`**
3. Kész exe: `dist\PyCleaner.exe`

### Kézi parancssorból
```cmd
pip install flask psutil pyinstaller
pyinstaller pycleaner.spec --clean --noconfirm
```

### Konzol nélküli verzió
```cmd
build_silent.bat
```

---

## 📁 Fájlstruktúra

```
pycleaner\
├── main.py              ← EXE belépési pont
├── app.py               ← Flask backend
├── pycleaner.spec       ← PyInstaller konfig
├── build.bat            ← Automatikus build
├── build_silent.bat     ← Konzol nélküli build
├── templates\index.html ← Teljes UI
├── static\favicon.ico
├── data\                ← config, history, schedule (auto)
└── backups\             ← ZIP mentések (auto)
```

---

## ⚙️ Funkciók

| Funkció | Leírás |
|---|---|
| 🧹 Tisztító | Temp, böngésző, logok, bélyegképek, lomtár, egyéni mappák |
| 📡 Élő monitor | CPU, RAM, Swap, Disk, Hálózat, top folyamatok |
| 👥 Duplikátumok | MD5-alapú keresés, egyenként törölhető |
| 🗝️ Registry | Hiányzó telepítők, autostart, MUI cache (Windows) |
| ⏰ Ütemező | Automatikus háttértisztítás |
| 💾 Backup | Törlés előtt ZIP mentés |
| 🌙 Téma | Sötét / világos váltó |
| 👤 Profilok | Több profil, jelszóvédelem |
| 📊 Export | HTML riport, JSON export |

---

## 🔧 EXE build követelmények

- Python 3.8+ (https://python.org)
- Windows 10/11
- Internet (csomagok letöltéséhez)

**Várható exe méret:** 15–30 MB

---

## ❓ GYIK

**Az exe lassú (10-20 mp)?**
Normális — PyInstaller az első indításkor kicsomagolja a fájlokat.

**Víruskereső blokkolja?**
Hamis riasztás lehet. Add hozzá kivételként, vagy futtasd a Python verzióját.

**Hol tárolódnak az adatok exe módban?**
Az exe melletti `data\` és `backups\` mappákban.

**Másolható másik gépre?**
Igen! `--onefile` — nem kell Python a célgépre.
