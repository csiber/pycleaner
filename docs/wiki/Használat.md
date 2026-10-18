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

## Registry (csak Windows)

A **Keresés** csak olvas. Három dolgot keres: árva eltávolító-bejegyzést (a program mappája és eltávolítója is hiányzik), nem létező programra mutató automatikus indítást, és a MUI-gyorsítótár elavult programneveit. A **Javítás** előtt a program minden érintett kulcsról `.reg` mentést készít — lásd [[Biztonság]].

## Finomhangolás (csak Windows)

- **Visszaállítási pont** — érdemes nagyobb módosítás előtt (rendszergazda kell).
- **Előtelepített alkalmazások** — a telepítettek előre kerülnek; az **Ajánlottak** gomb a biztonságosan eltávolíthatókat jelöli ki. Csak a saját felhasználódnál távolítja el őket, a Microsoft Store-ból visszatelepíthetők.
- **OneDrive eltávolítása** — előtte ellenőrizd, hogy minden fontos fájl szinkronizálva van-e.

## Ütemező

Bekapcsolva a választott időközönként (6 órától hetenkéntig) automatikusan tisztít, **amíg a PyCleaner fut**. Az ütemező csak biztonságos, nem végleges kategóriákat használhat.

## Előzmények

Minden tisztítás naplója (időpont, kategóriák, felszabadított hely, kézi/ütemezett), összesítéssel. Exportálható **HTML-riportként** vagy **JSON**-ként. A *Mentések* fülön a törlés előtti ZIP-mentések tölthetők le vagy törölhetők.

## Beállítások

Téma (rendszer / sötét / világos), kiemelőszín, profilok (név, jelszó a profilváltáshoz, mentési beállítások, egyéni mappák), frissítés-ellenőrzés. A bal alsó profilnévre kattintva gyorsan válthatsz profilt.
