# Változásnapló

A formátum a [Keep a Changelog](https://keepachangelog.com/hu/1.1.0/) ajánlását követi, a verziózás [SemVer](https://semver.org/lang/hu/).

## [5.1.0] — 2026-10-20

### Új
- **Gépállapot**: egy kattintásos felmérés — lemezek egészsége (SMART-állapot, kopás, hőmérséklet), szabad hely, vírusvédelem, Windows-frissítések, újraindításra váró frissítés, akkumulátor-kapacitás, indítópult — pontszámmal és javaslatokkal. Nyomtatható / PDF-be menthető riport, a Beállításokban megadható szervizfejléccel (név, elérhetőség, megjegyzés).
- **Indítópult**: a bejelentkezéskor induló programok (Run-kulcsok, Indítópult mappák, bejelentkezéskor induló ütemezett feladatok) kiadóval, ki/be kapcsolóval. A kikapcsolás a Feladatkezelővel azonos módon történik, semmi nem törlődik.
- **Programfrissítő**: a telepített programok frissítése a Windows beépített csomagkezelőjével (winget), kijelöléssel, csendben, élő naplóval.
- **Programok**: telepített programok listája méret, dátum és kiadó szerint; eltávolítás a program saját eltávolítójával, utána a maradék mappák felkínálása (alapból kijelöletlenül, Lomtárba).
- **Ütemező a Windows Feladatütemezőben**: az automatikus tisztítás akkor is lefut, ha a PyCleaner be van zárva (`--auto-clean`, ablak nélkül).
- **Tálcaikon**: a Beállításokban kérhető, hogy bezáráskor a program a tálcára kerüljön (gyors tisztítás és kilépés a menüből).
- **Angol nyelvű felület**: automatikusan a Windows nyelvét követi, a Beállításokban átállítható.

### Javítva
- A Gépállapot szabad-hely-szabálya nagy lemezen nem jelez tévesen (a százalék mellett az abszolút méretet is nézi).

## [5.0.1] — 2026-10-20

### Javítva
- Forrásból indításnál (`python main.py`) a hiányzó csomagok (pl. Flask) helyett nyers Python-hiba jelent meg. Most magyar üzenet mondja meg, mi hiányzik, és felajánlja a telepítést.
- Ha a `send2trash` csomag hiányzott, a „Lomtárba” művelet véglegesen törölt volna. Most hibát ad, és a fájlhoz nem nyúl. (A kiadott exe-ket nem érintette, azokban a csomag benne van.)

## [5.0.0] — 2026-10-18

Teljes újraírás: új felület, natív ablak, és a 4.x több veszélyes hibájának javítása. **Mindenkinek javasolt a frissítés.**

### Biztonsági és adatvédelmi javítások
- **A 4.x a „böngésző-gyorsítótár” tisztításakor a teljes Firefox-profilt törölte** (jelszavak, könyvjelzők, előzmények). Mostantól csak a profilok `cache2` mappája törlődik.
- A helyi szerver API-ja eddig bármely weboldalról elérhető volt (DNS-rebinding), és tetszőleges fájlt lehetett vele törölni. Most futásonként egyedi token, Host-ellenőrzés és szigorú CSP védi, fájlt pedig csak a program által kilistázott útvonalon lehet törölni.
- A törlés nem követ szimbolikus linket/junctiont, és a védett rendszer- és személyes mappákat egyéni mappaként sem fogadja el.
- Az indítási (Run) bejegyzések javítása kulcs helyett értéket töröl (a 4.x hibásan próbált kulcsot törölni), és a szóközt tartalmazó, idézőjel nélküli útvonalakat sem jelzi többé tévesen hiányzónak.
- Registry-módosítás előtt automatikus `.reg` mentés; az eltávolító-bejegyzést csak akkor jelzi árvának, ha a telepítési mappa és az eltávolító program is hiányzik.
- A profiljelszó PBKDF2-vel tárolódik (a régi sima szöveges jelszavak automatikusan átalakulnak), és a profilváltást a szerver is ellenőrzi.
- A HTML-riportban minden adat escape-elve van.

### Hibajavítások
- Exe-módban a beállítások, előzmények és mentések a futásonként törlődő ideiglenes mappába kerültek, így minden indításkor elvesztek. Mostantól a `%LOCALAPPDATA%\PyCleaner` mappában vannak.
- A OneDrive-eltávolítás PowerShellben `%SystemRoot%` szintaxist használt, ezért soha nem futott le; most a modern telepítési helyeket és a wingetet is megtalálja.
- A Candy Crush csomagnevek javítva (`king.com.*`).
- A Lomtár ürítése valós méretet és darabszámot jelent (Windows Shell API).
- A beolvasás pontosan azt méri, amit a tisztítás törölne (korhatár, kiterjesztés-szűrő).
- A „frissítés-ellenőrzés” valódi lett (GitHub Releases).

### Új
- Teljesen új, Windows 11-stílusú felület natív ablakban (WebView2), világos/sötét/rendszertéma, kiemelőszín.
- Áttekintés oldal lemezfoglaltsági sávval és gyors tisztítással.
- Új kategóriák: hibajelentések és memóriaképek, Windows Update gyorsítótár (a szolgáltatás leállításával), shader-tár; Vivaldi és Opera, valamint minden Chromium-profil.
- Figyelmeztetés futó böngészőre; rendszergazdai kategóriák jelölése, újraindítás rendszergazdaként.
- Nagy fájlok és duplikátumok: Lomtárba törlés, megmutatás az Intézőben, „mindenhol a legújabb marad”, mappatallózó.
- Gyorsabb duplikátumkeresés (első 64 KB előszűrés, BLAKE2b).
- Finomhangolás: kijelölhető alkalmazáslista telepítettségi állapottal, visszaállítási pont.
- Élő monitor: CPU/memória-grafikon, valós hálózati sebesség.
- A törlés előtti mentés kapcsolható és automatikusan ritkul (alapból ki — gyorsítótáraknál ritkán kell).
- Telepítő (Inno Setup, rendszergazdai jog nélkül), hordozható exe, ZIP, SHA256-összegek; automatikus kiadás GitHub Actionsszel.
- Tesztkészlet (pytest) és CI Windows + Linux alatt.

### Eltávolítva
- A „Legutóbbi dokumentumok” registry-tétel (adatvédelmi beállítás, nem hiba).
- A külön Napló oldal (a tisztítások az Előzményekben követhetők).

## [4.0] — 2026-02-28
- Windows Tweaks (OneDrive, bloatware), Kilépés gomb, verziókezelés.

## [3.0] — 2026-02-27
- Registry, duplikátumok, ütemező, profilok, mentés, HTML/JSON-export.

## [1.0] — 2026-02-27
- Első változat.
