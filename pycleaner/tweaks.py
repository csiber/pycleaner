"""Windows-finomhangolás: előtelepített alkalmazások és OneDrive eltávolítása."""

import json

from . import winapi

# (csomagnév, megjelenő név, alapból kijelölt?) — a játékokhoz/Xbox-fiókhoz szükséges
# komponensek (Xbox Identity Provider, Gaming Services) szándékosan nincsenek a listán.
APPS = [
    ("king.com.CandyCrushSaga", "Candy Crush Saga", True),
    ("king.com.CandyCrushSodaSaga", "Candy Crush Soda Saga", True),
    ("Microsoft.BingNews", "Hírek", True),
    ("Microsoft.BingWeather", "Időjárás", False),
    ("Microsoft.GetHelp", "Segítségkérés", True),
    ("Microsoft.Getstarted", "Tippek", True),
    ("Microsoft.MicrosoftSolitaireCollection", "Solitaire Collection", True),
    ("Microsoft.People", "Személyek", True),
    ("Microsoft.WindowsFeedbackHub", "Visszajelzési központ", True),
    ("Microsoft.ZuneMusic", "Groove Zene / Media Player", False),
    ("Microsoft.ZuneVideo", "Filmek és TV", False),
    ("Microsoft.SkypeApp", "Skype", True),
    ("Microsoft.MicrosoftOfficeHub", "Office/Microsoft 365 ajánló", True),
    ("Microsoft.Office.OneNote", "OneNote (áruházas)", False),
    ("Microsoft.YourPhone", "Telefonkapcsolat", False),
    ("Microsoft.WindowsMaps", "Térképek", False),
    ("Microsoft.Todos", "Microsoft To Do", False),
    ("Clipchamp.Clipchamp", "Clipchamp", True),
    ("Microsoft.549981C3F5F10", "Cortana", True),
    ("Microsoft.XboxApp", "Xbox Console Companion (régi)", False),
    ("Microsoft.XboxGamingOverlay", "Xbox Game Bar", False),
    ("Microsoft.MixedReality.Portal", "Mixed Reality Portal", True),
    ("Microsoft.BingSearch", "Bing keresés", False),
    ("MicrosoftCorporationII.QuickAssist", "Gyorssegéd", False),
]
KNOWN = {a[0] for a in APPS}


def installed_packages() -> set[str]:
    if not winapi.IS_WINDOWS:
        return set()
    r = winapi.powershell("Get-AppxPackage | Select-Object -ExpandProperty Name | ConvertTo-Json -Compress",
                          timeout=90)
    try:
        data = json.loads(r.stdout.strip() or "[]")
    except ValueError:
        return set()
    return set([data] if isinstance(data, str) else data)


def app_list() -> list[dict]:
    inst = installed_packages()
    return [{"id": pkg, "name": name, "default": default, "installed": pkg in inst}
            for pkg, name, default in APPS]


def remove_apps(ids: list[str]) -> list[dict]:
    if not winapi.IS_WINDOWS:
        return []
    results = []
    for pkg in ids:
        if pkg not in KNOWN:  # csak a saját listánk elemei — tetszőleges csomagnevet nem fogadunk el
            continue
        r = winapi.powershell(
            f"$p = Get-AppxPackage -Name '{pkg}'; if ($p) {{ $p | Remove-AppxPackage -ErrorAction Stop; 'REMOVED' }}"
            " else { 'ABSENT' }", timeout=180)
        out = r.stdout.strip()
        results.append({"id": pkg, "ok": r.returncode == 0 and ("REMOVED" in out or "ABSENT" in out),
                        "status": "removed" if "REMOVED" in out else "absent" if "ABSENT" in out else "error",
                        "error": (r.stderr.strip().splitlines() or [""])[0] if r.returncode else ""})
    return results


def uninstall_onedrive() -> tuple[bool, str]:
    if not winapi.IS_WINDOWS:
        return False, "Csak Windowson érhető el."
    script = r"""
Stop-Process -Name OneDrive -Force -ErrorAction SilentlyContinue
$cands = @("$env:SystemRoot\System32\OneDriveSetup.exe", "$env:SystemRoot\SysWOW64\OneDriveSetup.exe")
$cands += Get-ChildItem "$env:LOCALAPPDATA\Microsoft\OneDrive\*\OneDriveSetup.exe" -ErrorAction SilentlyContinue | ForEach-Object FullName
$cands += Get-ChildItem "$env:ProgramFiles\Microsoft OneDrive\*\OneDriveSetup.exe" -ErrorAction SilentlyContinue | ForEach-Object FullName
$setup = $cands | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if ($setup) { Start-Process $setup -ArgumentList '/uninstall' -Wait; "DONE:$setup" }
else {
  $w = Get-Command winget -ErrorAction SilentlyContinue
  if ($w) { winget uninstall --id Microsoft.OneDrive --silent --accept-source-agreements | Out-Null; 'DONE:winget' }
  else { 'NOTFOUND' }
}
"""
    r = winapi.powershell(script, timeout=300)
    out = r.stdout.strip()
    if "DONE" in out:
        return True, "A OneDrive eltávolítása lefutott. A felhőben tárolt fájlok megmaradnak a OneDrive-fiókban."
    if "NOTFOUND" in out:
        return False, "Nem találtam OneDrive-telepítőt — lehet, hogy már nincs telepítve."
    return False, (r.stderr.strip().splitlines() or ["Ismeretlen hiba."])[0]
