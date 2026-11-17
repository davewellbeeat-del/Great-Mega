@echo off
title GREAT MEGA - phone mode
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run: setting things up, please wait...
  py -m venv .venv
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
echo.
echo Phone mode needs a password. Set one in the app (Settings > Security) first.
echo Keep this window open while you use your phone.
echo.
".venv\Scripts\python.exe" app.py --lan
pause
