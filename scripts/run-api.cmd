@echo off
title LibrIA - API
cd /d "%~dp0..\apps\backend"
if not exist ".venv\Scripts\python.exe" (
  echo Falta configurar Python. Ejecuta setup.cmd desde la carpeta del proyecto.
  exit /b 1
)
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
