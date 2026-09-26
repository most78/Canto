@echo off
rem Canto: servidor local + navegador. Cierra esta ventana para apagarlo.
cd /d "%~dp0"
set PORT=8765
set PY=python
if exist ".venv\Scripts\python.exe" set PY=".venv\Scripts\python.exe"
rem Abre el navegador un segundo despues, cuando el servidor ya escucha.
start "" /min cmd /c "timeout /t 1 /nobreak >nul & start http://localhost:%PORT%/"
echo Canto en http://localhost:%PORT%/   (cierra esta ventana para apagarlo)
%PY% -m http.server %PORT% --bind 127.0.0.1
if errorlevel 1 (
  echo.
  echo No se pudo arrancar el servidor. Comprueba que Python esta instalado.
  pause
)
