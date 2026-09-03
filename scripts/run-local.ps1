[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendPath = Join-Path $projectRoot 'apps\backend'
$webPath = Join-Path $projectRoot 'apps\web'
$python = Join-Path $backendPath '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath (Join-Path $backendPath '.env'))) {
    throw 'El proyecto no está configurado. Ejecuta primero .\scripts\setup-windows.ps1'
}

# Cada servidor queda en una ventana visible para poder leer logs y detenerlo con Ctrl+C.
Start-Process powershell.exe -WorkingDirectory $backendPath -ArgumentList '-NoExit', '-Command', "& '$python' -m uvicorn app.main:app --reload"
Start-Process powershell.exe -WorkingDirectory $webPath -ArgumentList '-NoExit', '-Command', 'npm run dev'

Write-Host 'Backend:  http://localhost:8000/docs' -ForegroundColor Green
Write-Host 'Frontend: http://localhost:5173' -ForegroundColor Green
