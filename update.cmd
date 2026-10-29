@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-windows-safe.ps1"
if errorlevel 1 exit /b 1
echo Dependencias y configuracion local revisadas sin migrar ni iniciar servicios.
echo Este comando no ejecuta git pull. Ejecuta run.cmd para iniciar LibrIA.
