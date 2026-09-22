[CmdletBinding()]
param([switch]$PreflightOnly)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendPath = Join-Path $projectRoot 'apps\backend'
$webPath = Join-Path $projectRoot 'apps\web'
$python = Join-Path $backendPath '.venv\Scripts\python.exe'
$requirements = Join-Path $backendPath 'requirements.txt'
$lockfile = Join-Path $webPath 'package-lock.json'
$modulesPath = Join-Path $webPath 'node_modules'
$lockStamp = Join-Path $modulesPath '.libria-lock-sha256'

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath (Join-Path $backendPath '.env'))) {
    throw 'El proyecto no está configurado. Ejecuta primero .\scripts\setup-windows.ps1'
}

Write-Host 'Comprobando dependencias Python...' -ForegroundColor Cyan
& $python -m pip install --disable-pip-version-check -q -r $requirements
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias Python.' }
& $python -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Las dependencias Python tienen conflictos.' }

$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) { throw 'No se encontró npm. Instala Node.js y vuelve a abrir la terminal.' }
$lockHash = (Get-FileHash -LiteralPath $lockfile -Algorithm SHA256).Hash
$installedHash = if (Test-Path -LiteralPath $lockStamp) { (Get-Content -LiteralPath $lockStamp -Raw).Trim() } else { '' }
Push-Location $webPath
try {
    & $npm.Source ls --depth=0 --silent *> $null
    $npmHealthy = $LASTEXITCODE -eq 0
    if ($npmHealthy -and -not $installedHash) {
        # Reconoce una instalación previa sin forzar npm ci mientras Vite está abierto.
        Set-Content -LiteralPath $lockStamp -Value $lockHash -NoNewline
        $installedHash = $lockHash
    }
    if ($installedHash -ne $lockHash -or -not $npmHealthy) {
        if (Test-NetConnection -ComputerName 127.0.0.1 -Port 5173 -InformationLevel Quiet -WarningAction SilentlyContinue) {
            throw 'El frontend sigue abierto en el puerto 5173. Detenlo antes de actualizar sus dependencias.'
        }
        Write-Host 'Instalando dependencias del frontend...' -ForegroundColor Cyan
        & $npm.Source ci
        if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias del frontend.' }
        Set-Content -LiteralPath $lockStamp -Value $lockHash -NoNewline
    }
} finally { Pop-Location }

Write-Host 'Aplicando migraciones pendientes...' -ForegroundColor Cyan
Push-Location $backendPath
try {
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Falló la migración de la base de datos. No se iniciará el sistema.' }
} finally { Pop-Location }

Write-Host 'Preparación completa.' -ForegroundColor Green
if ($PreflightOnly) { return }

# Cada servidor queda en una ventana visible para poder leer logs y detenerlo con Ctrl+C.
if (Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -InformationLevel Quiet -WarningAction SilentlyContinue) {
    try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 3 } catch {
        throw 'El puerto 8000 está ocupado por otro proceso. Libéralo antes de iniciar LibrIA.'
    }
    if ($health.service -ne 'libria-api' -or $health.status -ne 'ok') {
        throw 'El puerto 8000 está ocupado por otro servicio. Libéralo antes de iniciar LibrIA.'
    }
    Write-Host 'Backend: ya estaba iniciado en http://localhost:8000' -ForegroundColor Yellow
} else {
    Start-Process powershell.exe -WorkingDirectory $backendPath -ArgumentList '-NoExit', '-Command', "& '$python' -m uvicorn app.main:app --reload"
    Write-Host 'Backend:  http://localhost:8000/docs' -ForegroundColor Green
}

if (Test-NetConnection -ComputerName 127.0.0.1 -Port 5173 -InformationLevel Quiet -WarningAction SilentlyContinue) {
    try { $webResponse = Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 3 } catch {
        throw 'El puerto 5173 está ocupado por otro proceso. Libéralo antes de iniciar LibrIA.'
    }
    if ($webResponse.Content -notmatch '/@vite/client' -or $webResponse.Content -notmatch 'LibrIA') {
        throw 'El puerto 5173 está ocupado por otro servicio. Libéralo antes de iniciar LibrIA.'
    }
    Write-Host 'Frontend: ya estaba iniciado en http://localhost:5173' -ForegroundColor Yellow
} else {
    Start-Process powershell.exe -WorkingDirectory $webPath -ArgumentList '-NoExit', '-Command', 'npm run dev'
    Write-Host 'Frontend: http://localhost:5173' -ForegroundColor Green
}
Push-Location $backendPath
try {
    & $python -c 'from app.core.config import get_settings; import sys; sys.exit(0 if len(get_settings().libria_demo_password) >= 8 else 1)'
    $demoPasswordReady = $LASTEXITCODE -eq 0
} finally { Pop-Location }
if ($demoPasswordReady) {
    Start-Process -FilePath $python -WorkingDirectory $backendPath -ArgumentList '-m', 'scripts.generate_posts' -WindowStyle Hidden
    Write-Host 'Generador: una publicación cada 30 segundos' -ForegroundColor Green
} else {
    Write-Warning 'Generador detenido: falta LIBRIA_DEMO_PASSWORD (mínimo 8 caracteres) en apps/backend/.env.'
}
