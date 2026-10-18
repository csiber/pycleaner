# Gyakori kérdések

**Tényleg felszabadít helyet, vagy csak „takarít”?**
A beolvasás pontosan megmutatja, mennyit. Böngészőknél, ideiglenes fájloknál és a Windows Update gyorsítótárában tipikusan néhány GB gyűlik össze. A gyorsítótárak idővel újra megtelnek — ez normális, ettől gyorsak a programok.

**A tisztítás után „X fájl kimaradt”. Baj?**
Nem. Ezeket épp használja egy program, ezért a Windows zárolja őket. Bezárás vagy újraindítás után legközelebb törlődnek.

**Lassabb lett a böngésző / a játék az első indításnál.**
A gyorsítótár újraépül — egyszeri jelenség. A shader-tárnál ezért nincs alapból kijelölve.

**Biztonságos a registry-tisztítás?**
A PyCleaner csak egyértelműen elavult bejegyzéseket jelez, és minden módosítás előtt mentést készít. Ettől függetlenül a registry „tisztítása” érdemi gyorsulást nem hoz; ott főleg rendrakásról van szó.

**Kell rendszergazdaként futtatni?**
Nem feltétlenül. Ami rendszergazdát igényel, azt a felület jelöli, és egy gombbal újraindíthatod emelt joggal.

**Miért kér hálózatot?**
Csak a frissítés-ellenőrzéshez (a GitHub kiadási listájának lekérése). A Beállításokban kikapcsolható; más hálózati forgalom nincs.

**Hol vannak a beállításaim?**
`%LOCALAPPDATA%\PyCleaner` (hordozható módban az exe melletti `PyCleanerData`). Itt van a `pycleaner.log` naplófájl is, ami hibabejelentéskor hasznos.

**Fut az ütemező, ha bezárom a programot?**
Nem. Ha rendszeres tisztítást szeretnél, tedd a PyCleanert az indítópultba (Win+R → `shell:startup`, ide egy parancsikon).

**Böngészőben nyílik meg, nem külön ablakban.**
Hiányzik a WebView2 futtatókörnyezet — lásd [[Telepítés]]. A böngészős mód is teljes értékű; ilyenkor a felületen a ⏻ gombbal állítható le a program.

**Linuxon / macOS-en is megy?**
Forrásból igen, az alapfunkciókkal (tisztítás, monitor, lemezelemző, duplikátumok). Kész csomag csak Windowsra van.
