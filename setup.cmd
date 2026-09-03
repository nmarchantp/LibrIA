@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-windows.ps1"
if errorlevel 1 (
  echo.
  echo La instalacion no pudo completarse. Revisa el error mostrado arriba.
  pause
  exit /b 1
)
echo.
echo LibrIA quedo configurado correctamente.
pause
