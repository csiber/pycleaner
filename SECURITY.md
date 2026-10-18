# Biztonsági szabályzat

## Támogatott verziók

Csak a legújabb kiadás kap javítást. A 4.x és korábbi verziók ismert, súlyos hibákat tartalmaznak (lásd a [CHANGELOG](CHANGELOG.md) 5.0.0-s bejegyzését) — kérlek, frissíts.

## Hiba bejelentése

Biztonsági hibát **ne nyilvános issue-ban** jelezz, hanem a GitHub [privát sebezhetőség-bejelentésével](https://github.com/csiber/pycleaner/security/advisories/new), vagy e-mailben: **info@promnet.hu**. Kérlek, írd le a hibát, a reprodukálás lépéseit és az érintett verziót. Néhány napon belül válaszolok.

## Felépítés röviden

A felület egy csak a `127.0.0.1` címen figyelő helyi webszerverről töltődik be. Az API futásonként generált tokent vár, ellenőrzi a `Host` fejlécet, és szigorú Content-Security-Policyt küld. Fájlt csak a program által előzőleg kilistázott útvonalon lehet törölni (és az is a Lomtárba kerül), registry-módosítás előtt kötelező a `.reg` mentés.
