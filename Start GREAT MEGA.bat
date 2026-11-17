@echo off
title GREAT MEGA
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run: setting things up, please wait...
  py -m venv .venv
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
".venv\Scripts\python.exe" desktop.py
