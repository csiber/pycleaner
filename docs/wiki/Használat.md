# Használat

## Áttekintés

Indításkor ez fogad: a rendszermeghajtó foglaltsága, az élő CPU-, memória- és hálózati terhelés, a legutóbbi tisztítás. A **Gép átvizsgálása** megméri, mennyi hely szabadítható fel; a sáv csíkos része mutatja ezt a lemezen belül. A **Gyors tisztítás** az alapból kijelölt, biztonságos kategóriákat takarítja (ideiglenes fájlok, böngésző-gyorsítótár, bélyegképek, hibajelentések).

## Tisztítás

1. Jelöld ki a kategóriákat (a részleteket lásd: [[Tisztítási kategóriák]]).
2. **Beolvasás** — kategóriánként megmutatja a méretet és a fájlok számát. A beolvasás csak olvas.
3. Igény szerint állíts be korhatárt (*csak a régebbiek, mint…*), hogy a friss fájlok maradjanak.
4. **Tisztítás.** A Lomtár és az egyéni mappák végleges törlése előtt megerősítést kér.

A használatban lévő fájlokat a Windows zárolja, ezeket a program kihagyja és a végén „kimaradt”-ként jelzi — ez normális. Ha egy böngésző fut, a kategória mellett figyelmeztetés jelenik meg.

## Élő monitor

Másfél másodpercenként frissülő CPU- és memóriagrafikon, lapozófájl, lemez, hálózati le/feltöltési sebesség, és a legtöbb memóriát használó nyolc folyamat.

## Lemezelemző

- **Meghajtók:** foglaltság és szabad hely minden meghajtón.
- **Személyes mappák:** Asztal, Dokumentumok, Letöltések, Képek, Videók, Zene, OneDrive, ideiglenes mappa — méret szerint rendezve. A névre kattintva megnyílik az Intézőben.
- **Nagy fájlok:** válassz mappát (Tallózás) és minimális méretet. A találatok a mappaikonnal megmutathatók az Intézőben, a kijelöltek a **Lomtárba** helyezhetők.

## Duplikátumok

Válassz mappát és minimális méretet, majd **Keresés**. A csoportokban a legújabb példány van elöl („legújabb” címke). A **Mindenhol a legújabb marad** gomb minden csoportban a többi példányt jelöli ki; a program nem engedi, hogy egy csoport összes példányát kijelöld. A törölt fájlok a Lomtárba kerülnek.

## Gépállapot (csak Windows)

A **Felmérés indítása** egy-két perc alatt átnézi a gépet, és csak olvas:

- lemezek: Windows-állapot (SMART), SSD-kopás, hőmérséklet;
- szabad hely meghajtónként, felszabadítható felesleges fájlok;
- vírusvédelem (Defender vagy más víruskereső) és az adatbázis kora;
- az utolsó Windows-frissítés, újraindításra váró frissítés, üzemidő;
- akkumulátor-kapacitás az eredetihez képest (laptopon);
- az indítópult terhelése, a memória mérete.

Az eredmény egy 0–100-as pontszám, a megállapítások súlyosság szerint (Sürgős / Figyelem / Rendben), mindegyik mellett javaslattal. A **Riport (nyomtatás / PDF)** gomb a böngészőben nyit meg egy nyomtatható oldalt — PDF-be a nyomtatási párbeszédben menthető. A riport fejlécébe és aljára a Beállítások → *Gépállapot-riport fejléce* részben adhatod meg a szerviz nevét, elérhetőségét és egy megjegyzést (pl. garancia, következő karbantartás).

## Indítópult (csak Windows)

A bejelentkezéskor induló programok: a Run-kulcsok (felhasználói és gépszintű), az Indítópult mappák, és a bejelentkezéskor induló ütemezett feladatok — kiadóval és paranccsal. A kapcsoló pontosan úgy kapcsol ki egy elemet, mint a Feladatkezelő *Indítás* lapja: a bejegyzés megmarad, bármikor visszakapcsolható. A gépszintű elemekhez rendszergazdai jog kell. A „hiányzó program” címke olyan bejegyzést jelöl, amelynek a programja már nincs a gépen.

## Programfrissítő (csak Windows)

A Windows beépített csomagkezelője (winget) alapján megmutatja, melyik telepített programhoz van újabb verzió. Jelöld ki, amit frissíteni szeretnél, és **Frissítés** — a programok egyenként, csendben frissülnek, a napló élőben látszik. Frissítés előtt érdemes bezárni az érintett programokat. Ha a winget hiányzik, a Microsoft Store *Alkalmazástelepítő* (App Installer) frissítése pótolja.

## Programok (csak Windows)

A telepített programok listája névvel, kiadóval, verzióval, mérettel és telepítési dátummal; kereshető és rendezhető. Az **Eltávolítás** a program saját eltávolítóját indítja el (MSI-csomagnál a Windows Installert) — ha kérdez, kövesd a lépéseit. Utána a PyCleaner felkínálja a megmaradt mappákat (a program telepítési mappája és a pontosan a nevét viselő AppData/ProgramData-mappák). Ezek **alapból nincsenek kijelölve**; amit kijelölsz, a Lomtárba kerül. Közös gyártói mappát (Microsoft, Google stb.) soha nem javasol.

## Registry (csak Windows)

A **Keresés** csak olvas. Három dolgot keres: árva eltávolító-bejegyzést (a program mappája és eltávolítója is hiányzik), nem létező programra mutató automatikus indítást, és a MUI-gyorsítótár elavult programneveit. A **Javítás** előtt a program minden érintett kulcsról `.reg` mentést készít — lásd [[Biztonság]].

## Finomhangolás (csak Windows)

- **Visszaállítási pont** — érdemes nagyobb módosítás előtt (rendszergazda kell).
- **Előtelepített alkalmazások** — a telepítettek előre kerülnek; az **Ajánlottak** gomb a biztonságosan eltávolíthatókat jelöli ki. Csak a saját felhasználódnál távolítja el őket, a Microsoft Store-ból visszatelepíthetők.
- **OneDrive eltávolítása** — előtte ellenőrizd, hogy minden fontos fájl szinkronizálva van-e.

## Ütemező

Bekapcsolva a választott időközönként (6 órától hetenkéntig) automatikusan tisztít. Windowson az *Akkor is fusson, ha a PyCleaner be van zárva* kapcsolóval a Windows Feladatütemezőjébe kerül egy feladat (`\PyCleaner\ScheduledClean`), amely ablak nélkül futtatja a tisztítást; kikapcsoláskor a feladat törlődik. Az ütemező csak biztonságos, nem végleges kategóriákat használhat.

Ha a Beállításokban bekapcsolod a *Bezáráskor a tálcára kerüljön* opciót, az ablak bezárása után a PyCleaner a tálcán fut tovább; a tálcaikon menüjéből megnyitható, gyors tisztítás indítható, és ott lehet kilépni.

## Előzmények

Minden tisztítás naplója (időpont, kategóriák, felszabadított hely, kézi/ütemezett), összesítéssel. Exportálható **HTML-riportként** vagy **JSON**-ként. A *Mentések* fülön a törlés előtti ZIP-mentések tölthetők le vagy törölhetők.

## Beállítások

Nyelv (automatikus / magyar / angol), téma (rendszer / sötét / világos), kiemelőszín, tálcára zárás, profilok (név, jelszó a profilváltáshoz, mentési beállítások, egyéni mappák), frissítés-ellenőrzés. A bal alsó profilnévre kattintva gyorsan válthatsz profilt.
