# PyCleaner — Python CCleaner-klón

## Telepítés

```bash
pip install flask
```

## Indítás

```bash
python app.py
```

Ezután nyisd meg a böngészőben: **http://localhost:5000**

---

## Funkciók

| Funkció | Leírás |
|---|---|
| 🧹 **Ideiglenes fájlok törlése** | Temp mappák (%TEMP%, /tmp) |
| 🌐 **Böngésző gyorsítótár** | Chrome, Firefox, Edge cache |
| 📄 **Log fájlok törlése** | .log, .old, .bak fájlok |
| 🗑️ **Lomtár ürítése** | Recycle Bin / ~/.Trash |
| 📊 **Lemez elemző** | Mappák méretének vizualizációja |
| 🖥️ **Rendszerinformáció** | OS, lemezhasználat, donut chart |
| 📋 **Eseménynapló** | Minden művelet naplózva |

## Kompatibilitás

- **Windows** ✅ — Temp, %LOCALAPPDATA%, Edge/Chrome/Firefox, Lomtár
- **Linux** ✅ — /tmp, ~/.cache, Firefox/Chrome, ~/.Trash
- **macOS** ✅ — /tmp, ~/Library/Caches, ~/.Trash

## Figyelem

A "Tisztítás" gomb **véglegesen törli** a kiválasztott fájlokat. A lomtár ürítése előtt győződj meg róla, hogy nincs szükséged a benne lévő fájlokra!
