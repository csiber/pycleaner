@echo off
chcp 65001 >nul
title PyCleaner — Silent EXE Build (konzol nélküli)

echo.
echo  Konzol nélküli (tray-style) verzió buildele...
echo  FIGYELEM: Hibák nem lesznek láthatók indításkor!
echo.

pip install flask psutil pyinstaller --quiet

:: Módosított spec futtatása console=False opcióval
pyinstaller main.py ^
    --onefile ^
    --noconsole ^
    --name PyCleaner_Silent ^
    --icon static\favicon.ico ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --hidden-import flask ^
    --hidden-import jinja2 ^
    --hidden-import werkzeug ^
    --hidden-import psutil ^
    --hidden-import winreg ^
    --hidden-import click ^
    --exclude-module tkinter ^
    --exclude-module matplotlib ^
    --clean ^
    --noconfirm

if exist "dist\PyCleaner_Silent.exe" (
    echo.
    echo  ✅ dist\PyCleaner_Silent.exe elkészült!
    echo     Dupla kattintással indul, majd megnyílik a böngésző.
    explorer dist
) else (
    echo  HIBA: Build sikertelen.
)
pause
