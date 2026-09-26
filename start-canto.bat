@echo off
rem Canto: servidor local + navegador. Cierra esta ventana para apagarlo.
cd /d "%~dp0"
set PORT=8765
set PY=python
if exist ".venv\Scripts\python.exe" set PY=".venv\Scripts\python.exe"
rem Abre el navegador un segundo despues, cuando el servidor ya escucha.
start "" /min cmd /c "timeout /t 1 /nobreak >nul & start http://localhost:%PORT%/"
rem serve.py = http.server sin cache (siempre la ultima version del codigo)
%PY% serve.py %PORT%
if errorlevel 1 (
  echo.
  echo No se pudo arrancar el servidor. Comprueba que Python esta instalado.
  pause
)
