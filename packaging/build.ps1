# PyCleaner — Windows-build helyben. Futtatás a repó gyökeréből PowerShellben:
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
# Eredmény: dist\PyCleaner\ (mappás), dist\PyCleaner-portable.exe, és ha van Inno Setup: dist\PyCleaner-<ver>-Setup.exe
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) { py -3 -m venv .venv }
& .venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& .venv\Scripts\python.exe -m pip install -r requirements-dev.txt --quiet

Write-Host "Tesztek..." -ForegroundColor Cyan
& .venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "A tesztek elbuktak." }

$version = & .venv\Scripts\python.exe packaging\make_version_info.py --print
Write-Host "PyCleaner $version build..." -ForegroundColor Cyan

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
$env:PYC_ONEFILE = ""
& .venv\Scripts\pyinstaller.exe packaging\pycleaner.spec --noconfirm --clean
$env:PYC_ONEFILE = "1"
& .venv\Scripts\pyinstaller.exe packaging\pycleaner.spec --noconfirm
$env:PYC_ONEFILE = ""

$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") |
  Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) { & $iscc /Qp "/DAppVersion=$version" packaging\installer.iss }
else { Write-Warning "Inno Setup 6 nincs telepítve — a telepítő kimarad (winget install JRSoftware.InnoSetup)." }

Get-ChildItem dist | Format-Table Name, Length
