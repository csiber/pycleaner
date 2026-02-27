@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title PyCleaner - EXE Build

echo.
echo ======================================================
echo        PyCleaner v3.0 - EXE Builder
echo ======================================================
echo.

:: Python ellenőrzés
echo [1/5] Python ellenorzese...
python --version >nul 2>&1
if errorlevel 1 (
    echo HIBA: Python nem talalhato! https://python.org
    pause
    exit /b 1
)
python --version
echo OK
echo.

:: pip csomagok
echo [2/5] Csomagok telepitese...
pip install flask psutil pyinstaller --quiet --upgrade
if errorlevel 1 (
    echo HIBA: pip install sikertelen!
    pause
    exit /b 1
)
echo OK
echo.

:: regi build torles
echo [3/5] Regi build torlese...
if exist "dist\PyCleaner.exe" del /f /q "dist\PyCleaner.exe"
if exist "build" rmdir /s /q "build"
echo OK
echo.

:: build
echo [4/5] EXE build...
pyinstaller pycleaner.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo HIBA: build sikertelen!
    pause
    exit /b 1
)
echo.

:: ellenorzes
echo [5/5] Ellenorzes...
if not exist "dist\PyCleaner.exe" (
    echo HIBA: exe nem jott letre!
    pause
    exit /b 1
)

for %%A in ("dist\PyCleaner.exe") do (
    set /a size_mb=%%~zA/1048576
)

echo.
echo ======================================================
echo  BUILD SIKERES
echo  Fajl: dist\PyCleaner.exe
echo  Meret: !size_mb! MB
echo  Inditas: dupla kattintas
echo  URL: http://localhost:5000
echo ======================================================
echo.

explorer dist
pause