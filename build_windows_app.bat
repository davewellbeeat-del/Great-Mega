@echo off
title Build GREAT MEGA app
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" py -m venv .venv
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
set EXTRA=
".venv\Scripts\python.exe" -c "import MetaTrader5" 2>nul && set EXTRA=--collect-all MetaTrader5
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --onefile --windowed --name GreatMega ^
  --icon "static\icons\app.ico" %EXTRA% ^
  --add-data "templates;templates" --add-data "static;static" desktop.py
echo.
echo If it worked, your app is: dist\GreatMega.exe
echo (Windows may warn about an unknown publisher. Choose "More info" then "Run anyway".)
pause
