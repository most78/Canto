@echo off
rem Canto LEGACY (PySide6). La version actual es la web: start-canto.bat en la raiz.
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo Falta el entorno .venv. Ver legacy\requirements.txt.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" legacy\src\main.py
if errorlevel 1 pause
