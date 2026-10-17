@echo off
setlocal
title LibrIA - Detener servicios
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-local.ps1"
if errorlevel 1 (
  echo.
  echo No se pudieron detener todos los procesos de LibrIA.
  pause
  exit /b 1
)
echo.
pause
