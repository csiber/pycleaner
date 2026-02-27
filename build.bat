@echo off
chcp 65001 >nul
title PyCleaner — EXE Build

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║         PyCleaner v3.0 — EXE Builder                ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: ── Python ellenőrzés ────────────────────────────────────────────
echo [1/5] Python ellenőrzése...
python --version >nul 2>&1
if errorlevel 1 (
    echo  HIBA: Python nem található! Töltsd le: https://python.org
    pause
    exit /b 1
)
python --version
echo  OK
echo.

:: ── pip csomagok ─────────────────────────────────────────────────
echo [2/5] Szükséges csomagok telepítése...
pip install flask psutil pyinstaller --quiet --upgrade
if errorlevel 1 (
    echo  HIBA: Csomagok telepítése sikertelen!
    pause
    exit /b 1
)
echo  OK: flask, psutil, pyinstaller
echo.

:: ── Régi build törlése ───────────────────────────────────────────
echo [3/5] Régi build mappa törlése...
if exist "dist\PyCleaner.exe" del /f /q "dist\PyCleaner.exe"
if exist "build" rmdir /s /q "build"
echo  OK
echo.

:: ── PyInstaller build ────────────────────────────────────────────
echo [4/5] Exe összeállítása (ez 1-3 percig tarthat)...
echo.
pyinstaller pycleaner.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo  HIBA: A build sikertelen! Lásd a hibaüzenetet fentebb.
    echo  Tipp: Futtasd a parancsot admin jogokkal!
    pause
    exit /b 1
)
echo.

:: ── Ellenőrzés ───────────────────────────────────────────────────
echo [5/5] Build ellenőrzése...
if not exist "dist\PyCleaner.exe" (
    echo  HIBA: Az exe nem jött létre!
    pause
    exit /b 1
)

:: Fájlméret
for %%A in ("dist\PyCleaner.exe") do (
    set /a size_mb=%%~zA/1048576
    echo  Méret: ~!size_mb! MB
)

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║  ✅  BUILD SIKERES!                                  ║
echo  ║                                                      ║
echo  ║  Fájl:  dist\PyCleaner.exe                          ║
echo  ║                                                      ║
echo  ║  Indítás: dupla kattintás a PyCleaner.exe-re        ║
echo  ║  Megnyílik: http://localhost:5000                    ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: Build mappa megnyitása
explorer dist

pause
