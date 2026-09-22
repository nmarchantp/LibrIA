@echo off
setlocal
cd /d "%~dp0"
git pull --ff-only
if errorlevel 1 (
  echo No se pudo actualizar el repositorio. Revisa Git antes de continuar.
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run-local.ps1" -PreflightOnly
if errorlevel 1 exit /b 1
echo Repositorio y entorno local listos. Ejecuta run.cmd para iniciar LibrIA.
