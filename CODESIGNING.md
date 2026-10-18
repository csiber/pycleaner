# Kódaláírási szabályzat / Code signing policy

**Magyarul.** A PyCleaner Windows-fájljait (telepítő, hordozható exe, a ZIP-ben lévő `PyCleaner.exe`) a GitHub Actions
építi automatikusan, közvetlenül ebből a nyilvános tárolóból (`.github/workflows/release.yml`, `v*` címkék). Aláírást csak
az így készült, nyilvánosan kiadott fájlok kapnak; helyi vagy kézzel készített build soha. Ingyenes kódaláírás:
[SignPath.io](https://about.signpath.io), tanúsítvány: [SignPath Foundation](https://signpath.org).

- **Karbantartó, fejlesztő és jóváhagyó:** Polyák Csaba ([@csiber](https://github.com/csiber), info@promnet.hu). Minden aláírási kérést ő hagy jóvá; külső hozzájárulás csak az ő átnézése után kerül a `main` ágba.
- **Adatvédelem:** a program a felhasználó gépéről semmilyen adatot nem küld el. Egyetlen hálózati kérése a frissítés-ellenőrzés, amely a GitHub nyilvános API-jától lekéri a legújabb kiadás verziószámát (`api.github.com/repos/csiber/pycleaner/releases/latest`); ez a Beállításokban kikapcsolható. A felület kizárólag a helyi gépen (`127.0.0.1`) érhető el.
- **Mit csinál a program:** ideiglenes fájlokat és gyorsítótárakat töröl, a felhasználó által kijelölt fájlokat a Lomtárba helyezi, a Windows rendszerleíró adatbázisában mentés után elavult bejegyzéseket javít, és kérésre előtelepített alkalmazásokat távolít el. Részletek: [wiki](https://github.com/csiber/pycleaner/wiki).

**English.** Free code signing provided by [SignPath.io](https://about.signpath.io), certificate by [SignPath Foundation](https://signpath.org).
Windows binaries (installer, portable exe and the `PyCleaner.exe` inside the ZIP) are built automatically by GitHub Actions from this
public repository (`.github/workflows/release.yml`, tags `v*`); only those released builds are signed, never local builds.

- **Committer, reviewer and approver:** Csaba Polyák ([@csiber](https://github.com/csiber)). Every signing request is approved manually by him.
- **Privacy:** this program will not transfer any information to other networked systems. Its only network request is an optional update check that reads the latest release version from the public GitHub API; it can be disabled in Settings. The user interface is served on `127.0.0.1` only.
