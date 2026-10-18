# Biztonság

A PyCleaner alapelve: **inkább hagyjon meg valamit, mint hogy olyat töröljön, amit nem kéne.**

## Amihez soha nem nyúl

- Böngészők személyes adatai: jelszavak, előzmények, sütik, könyvjelzők, bővítmények. (A 4.x-ben volt egy hiba, ami a teljes Firefox-profilt törölhette — az 5.0-ban ez javítva, és teszt őrzi.)
- Szimbolikus linkek és junctionök célpontjai — a törlés nem lép át rajtuk.
- Védett mappák: bármely meghajtó gyökere, `Windows`, `Program Files`, `ProgramData`, a felhasználói profil gyökere, `AppData`, Asztal, Dokumentumok, Letöltések, Képek, Videók, Zene. Ezeket egyéni mappaként sem lehet megadni.
- A program nem telepít szolgáltatást, nem módosít indítási beállítást, és nem küld adatot.

## Visszafordítható lépések

| Művelet | Visszaállítás |
|---|---|
| Nagy fájl / duplikátum törlése | A **Lomtárba** kerül. |
| Registry-javítás | Előtte `.reg` mentés készül a `%LOCALAPPDATA%\PyCleaner\registry-backups` mappába; a fájlra duplán kattintva visszaállítható. Ha a mentés nem sikerül, a program nem módosít. |
| Gyorsítótár-tisztítás | Opcionális ZIP-mentés (Beállítások → *Mentés törlés előtt*). |
| Alkalmazás eltávolítása | A Microsoft Store-ból visszatelepíthető. |
| Bármi más | A Finomhangolás oldalon előtte készíts **visszaállítási pontot**. |

Véglegesen csak a **Lomtár ürítése** és az **egyéni mappák** törlése töröl — mindkettő előtt megerősítést kér.

## A helyi szerver védelme

A felület egy beágyazott ablakban fut, amely a gépen futó, csak a `127.0.0.1` címen figyelő szerverhez kapcsolódik. Hogy egy rosszindulatú weboldal ne tudja ezt távolról vezérelni:

- minden API-hívás egy **futásonként véletlenszerűen generált tokent** vár, amit csak a saját felület ismer;
- a szerver elutasít minden kérést, amelynek `Host` fejléce nem `127.0.0.1` / `localhost` (DNS-rebinding elleni védelem);
- szigorú **Content-Security-Policy**: csak saját szkript, külső erőforrás nincs;
- a fájltörlő végpont csak azokat az útvonalakat fogadja el, amelyeket a program előzőleg maga listázott ki;
- a registry-javító végpont csak a legutóbbi keresés találatait ismeri, tetszőleges kulcsot nem;
- az alkalmazás-eltávolító csak a beépített listán szereplő csomagneveket fogadja el.

## Profiljelszó

A profilváltás jelszóval védhető. A jelszó PBKDF2-SHA256-tal (200 000 kör) tárolódik. Ez a funkció családi gépen a véletlen váltást akadályozza meg — **nem titkosítás**.

## Hibabejelentés

Lásd [SECURITY.md](https://github.com/csiber/pycleaner/blob/main/SECURITY.md).
