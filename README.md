# PyCleaner v4.0 — Rendszertisztító & Tweak

## 🚀 Újdonságok a v4.0-ban
- **Windows Tweaks:** OneDrive és bloatware (Candy Crush, stb.) eltávolító.
- **Kilépés funkció:** Teljes leállás, nem marad háttérfolyamat.
- **Verzió kezelés:** Frissítés ellenőrzése és verzió információk.
- **Stabilitási javítások:** Jobb registry és fájlkezelés.

## 🚀 Gyors indítás (Python)
```bash
pip install flask psutil
python main.py
# Böngésző: automatikusan megnyílik
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

---

## ⚙️ Funkciók

| Funkció | Leírás |
|---|---|
| 🧹 Tisztító | Temp, böngésző, logok, bélyegképek, lomtár, egyéni mappák |
| 🛠️ Tweaks | OneDrive eltávolítás, bloatware tisztítás (Candy Crush, Xbox, stb.) |
| 📡 Élő monitor | CPU, RAM, Swap, Disk, Hálózat, top folyamatok |
| 👥 Duplikátumok | MD5-alapú keresés, egyenként törölhető |
| 🗝️ Registry | Hiányzó telepítők, autostart, MUI cache (Windows) |
| ⏰ Ütemező | Automatikus háttértisztítás |
| ❌ Kilépés | Teljes leállás a felületről |
| 💾 Backup | Törlés előtt ZIP mentés |
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
