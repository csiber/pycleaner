# Tisztítási kategóriák

A beolvasás pontosan azt méri, amit a tisztítás törölne. Minden kategória csak a felsorolt mappák **tartalmát** üríti; magát a mappát meghagyja, szimbolikus linket és junctiont nem követ.

| Kategória | Alapból | Windows-mappák | Megjegyzés |
|---|:-:|---|---|
| Ideiglenes fájlok | ✅ | `%TEMP%`, `%LOCALAPPDATA%\Temp`, `%WINDIR%\Temp` | A használatban lévő fájlok kimaradnak. |
| Böngésző-gyorsítótár | ✅ | Chrome, Edge, Brave, Vivaldi: minden profil `Cache`, `Code Cache`, `GPUCache`; Opera; Firefox: minden profil `cache2` | Jelszó, előzmény, süti, könyvjelző **nem** törlődik. |
| Bélyegkép-gyorsítótár | ✅ | `%LOCALAPPDATA%\Microsoft\Windows\Explorer` — csak `thumbcache_*.db`, `iconcache_*.db` | Az Intéző újraépíti. |
| Hibajelentések és memóriaképek | ✅ | `%LOCALAPPDATA%\CrashDumps`, WER `ReportArchive`/`ReportQueue` (felhasználói és gépszintű), `%WINDIR%\Minidump` | |
| Régi naplófájlok | – | `%WINDIR%\Logs` (`.log .old .bak .etl`, legalább 7 napos), `%WINDIR%\Panther` (`.log`, 30 napos) | Rendszergazda kell. |
| Windows Update gyorsítótár | – | `%WINDIR%\SoftwareDistribution\Download` + kézbesítésoptimalizálás | Rendszergazda kell. A törlés idejére leállítja a `wuauserv` és `bits` szolgáltatást, utána újraindítja. |
| Shader-gyorsítótár | – | `%LOCALAPPDATA%\D3DSCache`, NVIDIA `DXCache`/`GLCache`, AMD `DxCache`/`DxcCache`/`VkCache` | A játékok első indításkor újraépítik — rövid akadozás lehet. |
| Lomtár | – | Az összes meghajtó Lomtára (Shell API) | **Végleges**, megerősítést kér. |
| Egyéni mappák | – | A Beállításokban megadott mappák | **Végleges**, megerősítést kér. Védett mappát nem fogad el. |

## Linux és macOS

Forrásból futtatva az alábbiak érhetők el: ideiglenes fájlok (`/tmp` és `/var/tmp` csak 1, illetve 7 napnál régebbi, nem rejtett elemek), böngésző-gyorsítótár (`~/.cache/…`, `~/Library/Caches/…`), bélyegképek, rotált naplók (`/var/log/*.gz`, `*.1`…), összeomlási jelentések, Lomtár.

## Korhatár

A Tisztítás oldalon beállíthatod, hogy csak 1 napnál, 1 hétnél vagy 1 hónapnál régebbi fájlok törlődjenek. Egyes kategóriáknak saját minimuma van (pl. naplók: 7 nap) — a kettő közül a nagyobb érvényes.
