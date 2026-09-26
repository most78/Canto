@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Falta el entorno local. Consulta README.md para instalarlo.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" src\main.py
if errorlevel 1 pause
