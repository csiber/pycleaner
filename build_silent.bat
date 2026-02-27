@echo off
setlocal
chcp 65001 >nul
title PyCleaner - Silent EXE Build

echo.
echo Konzol nelkuli (tray-style) verzio build...
echo FIGYELEM: Hibak nem lesznek lathatok inditaskor!
echo.

pip show pyinstaller >nul 2>&1 || pip install pyinstaller
pip show flask >nul 2>&1 || pip install flask
pip show psutil >nul 2>&1 || pip install psutil

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
    echo BUILD OK: dist\PyCleaner_Silent.exe
    explorer dist
) else (
    echo HIBA: Build sikertelen.
)

pause