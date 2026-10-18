# SignPath-beállítás

A kiadási workflow (`.github/workflows/release.yml`) magától aláír, ha be van állítva:

| Hol | Név | Érték |
|---|---|---|
| Repository → Settings → Secrets → Actions | `SIGNPATH_API_TOKEN` | a SignPath CI-felhasználó API-tokenje |
| Repository → Settings → Variables → Actions | `SIGNPATH_ORGANIZATION_ID` | a SignPath-szervezet azonosítója |
| (opcionális) Variables | `SIGNPATH_PROJECT_SLUG` | alapból `pycleaner` |
| (opcionális) Variables | `SIGNPATH_POLICY_SLUG` | alapból `release-signing` |

A SignPath-projektben két artifact configuration kell, az itteni XML-ekkel: `binaries` és `installer`.
Trusted build system: GitHub.com connector. Ha a token hiányzik, a workflow aláírás nélkül épít és ad ki.

A folyamat: PyInstaller → `PyCleaner.exe` és `PyCleaner-portable.exe` aláírása → Inno Setup a már aláírt exe-vel →
telepítő aláírása → hitelesség-ellenőrzés (`Get-AuthenticodeSignature`) → GitHub-kiadás.
Az aláírási kéréseket a SignPath webes felületén jóvá kell hagyni (a workflow addig vár, legfeljebb 1 órát).
