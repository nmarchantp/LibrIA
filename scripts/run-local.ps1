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
Start-Process powershell.exe -WorkingDirectory $backendPath -ArgumentList '-NoExit', '-Command', "& '$python' -m uvicorn app.main:app --reload"
Start-Process powershell.exe -WorkingDirectory $webPath -ArgumentList '-NoExit', '-Command', 'npm run dev'
Start-Process -FilePath $python -WorkingDirectory $backendPath -ArgumentList '-m', 'scripts.generate_posts' -WindowStyle Hidden

Write-Host 'Backend:  http://localhost:8000/docs' -ForegroundColor Green
Write-Host 'Frontend: http://localhost:5173' -ForegroundColor Green
Write-Host 'Generador: una publicación cada 30 segundos' -ForegroundColor Green
