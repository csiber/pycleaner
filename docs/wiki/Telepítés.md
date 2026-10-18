# Telepítés

## Követelmények

- Windows 10 (1809 vagy újabb) vagy Windows 11, 64 bites
- Microsoft Edge **WebView2** futtatókörnyezet — Windows 11-en és a frissített Windows 10-en gyárilag megvan. Ha hiányzik, a PyCleaner a böngészőben nyílik meg; a natív ablakhoz [innen telepíthető](https://developer.microsoft.com/microsoft-edge/webview2/).

## Melyik fájlt töltsem le?

A [kiadások oldalán](https://github.com/csiber/pycleaner/releases/latest):

| Fájl | Leírás |
|---|---|
| `PyCleaner-<verzió>-Setup.exe` | **Ajánlott.** Telepítő magyar varázslóval. Alapból csak a te felhasználódnak telepít, ehhez nem kell rendszergazdai jog; a varázslóban kérheted a gépszintű telepítést is. |
| `PyCleaner-<verzió>-portable.exe` | Egyetlen exe, telepítés nélkül. Az első indítás pár másodperccel lassabb, mert kicsomagolja magát. |
| `PyCleaner-<verzió>-win64.zip` | Kicsomagolható mappa; a hordozhatónál gyorsabban indul. |
| `SHA256SUMS.txt` | Ellenőrzőösszegek. PowerShellben: `Get-FileHash .\PyCleaner-5.0.0-Setup.exe` |

## „A Windows megvédte a számítógépet” (SmartScreen)

A kiadások még nincsenek kódaláírással ellátva, ezért a SmartScreen ismeretlen kiadóként jelezheti. Ilyenkor: **További információ → Futtatás mindenképp**. Ha bizonytalan vagy, ellenőrizd az SHA256-összeget, vagy futtasd [forrásból](Fejlesztés).

Néhány víruskereső a PyInstallerrel készült programokat tévesen gyanúsnak jelöli. A build UPX-tömörítés nélkül készül, hogy ez minél ritkább legyen; ha mégis előfordul, kérlek jelezd egy issue-ban a víruskereső nevével.

## Rendszergazdaként futtatás

A legtöbb funkció normál jogokkal működik. Rendszergazda kell a **Windows Update gyorsítótárhoz**, a **rendszernaplókhoz**, a **visszaállítási ponthoz** és a gépszintű (HKLM) registry-elemekhez. A programból is kérheted: *Áttekintés* vagy *Finomhangolás* → **Újraindítás rendszergazdaként**.

## Hordozható mód

Ha az exe mellett van egy üres `portable.txt` fájl, a PyCleaner minden adatát (beállítások, előzmények, mentések) a mellette lévő `PyCleanerData` mappába írja — pendrive-ról futtatva így semmi nem marad a gépen.

## Eltávolítás

*Beállítások → Alkalmazások → PyCleaner → Eltávolítás.* A beállításaid és mentéseid a `%LOCALAPPDATA%\PyCleaner` mappában maradnak; ha ezekre sincs szükséged, töröld kézzel.

## Frissítés

A program indításkor megnézi, van-e újabb kiadás (kikapcsolható a Beállításokban), és az Áttekintésen jelzi. Telepítős változatnál egyszerűen futtasd az új telepítőt — a beállítások megmaradnak.
