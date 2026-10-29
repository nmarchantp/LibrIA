[CmdletBinding()]
param([switch]$PreflightOnly, [switch]$DemoPosts)

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
    throw 'El proyecto no está configurado. Ejecuta primero .\setup.cmd.'
}

# Este modo es estrictamente de solo lectura. No instala dependencias, no
# completa .env, no migra y no inicia ningún proceso de la aplicación.
if ($PreflightOnly) {
    Write-Host 'Preflight de solo lectura.' -ForegroundColor Cyan
    & $python -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependencias Python incompletas. Ejecuta .\update.cmd.' }

    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) { throw 'No se encontró npm. Instala Node.js y vuelve a abrir la terminal.' }
    Push-Location $webPath
    try {
        & $npm.Source ls --depth=0 --silent *> $null
        if ($LASTEXITCODE -ne 0) { throw 'Dependencias frontend incompletas. Ejecuta .\update.cmd.' }
    } finally { Pop-Location }

    Push-Location $backendPath
    try {
        & $python -m alembic current --check-heads
        if ($LASTEXITCODE -ne 0) {
            throw 'La base tiene migraciones pendientes. Respalda y usa .\setup.cmd -AllowMainDatabaseMigration.'
        }
        & $python -c 'from app.core.config import get_settings; get_settings()'
        if ($LASTEXITCODE -ne 0) { throw 'La configuración local no es válida.' }
    } finally { Pop-Location }
    Write-Host 'Preflight correcto: no se modificaron archivos ni base y no se iniciaron procesos.' -ForegroundColor Green
    return
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
        Set-Content -LiteralPath $lockStamp -Value $lockHash -NoNewline
        $installedHash = $lockHash
    }
    if ($installedHash -ne $lockHash -or -not $npmHealthy) {
        if (Test-NetConnection -ComputerName 127.0.0.1 -Port 5173 -InformationLevel Quiet -WarningAction SilentlyContinue) {
            throw 'El frontend sigue abierto en 5173. Detenlo antes de actualizar dependencias.'
        }
        & $npm.Source ci
        if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias frontend.' }
        Set-Content -LiteralPath $lockStamp -Value $lockHash -NoNewline
    }
} finally { Pop-Location }

Write-Host 'Comprobando que la base esté en la revisión Alembic actual...' -ForegroundColor Cyan
Push-Location $backendPath
try {
    & $python -m alembic current --check-heads
    if ($LASTEXITCODE -ne 0) {
        throw 'La base tiene migraciones pendientes. Respalda y usa .\setup.cmd -AllowMainDatabaseMigration antes de iniciar.'
    }
} finally { Pop-Location }

& (Join-Path $PSScriptRoot 'prepare-ai.ps1')

# Scheduler y worker son procesos separados de FastAPI para no duplicar ETL ni consumo.
Push-Location $backendPath
try {
    $runtimeJson = & $python -c "import json; from app.core.config import get_settings; s=get_settings(); free=s.gemini_free_test_mode and s.app_env in ('development','test'); print(json.dumps(dict(scheduler=s.analytics_scheduler_enabled or s.projection_scheduler_enabled, worker=s.gemini_worker_enabled and (s.gemini_paid_service_confirmed or free))))"
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo leer la configuración de procesos.' }
    $runtime = $runtimeJson | ConvertFrom-Json
} finally { Pop-Location }
$runningProcesses = @(Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and $_.CommandLine.IndexOf($projectRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0
})
if ($runtime.scheduler -and -not ($runningProcesses | Where-Object { $_.CommandLine -match 'scripts\.run_scheduler' })) {
    Start-Process -FilePath $python -WorkingDirectory $backendPath -ArgumentList '-m', 'scripts.run_scheduler' -WindowStyle Hidden
    Write-Host 'Scheduler ETL/proyecciones iniciado.' -ForegroundColor Green
}
if ($runtime.worker -and -not ($runningProcesses | Where-Object { $_.CommandLine -match 'scripts\.run_gemini_worker' })) {
    Start-Process -FilePath $python -WorkingDirectory $backendPath -ArgumentList '-m', 'scripts.run_gemini_worker' -WindowStyle Hidden
    Write-Host 'Worker Gemini iniciado.' -ForegroundColor Green
}

if (Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -InformationLevel Quiet -WarningAction SilentlyContinue) {
    try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 3 } catch {
        throw 'El puerto 8000 está ocupado por otro proceso.'
    }
    if ($health.service -ne 'libria-api' -or $health.status -ne 'ok') { throw 'El puerto 8000 pertenece a otro servicio.' }
    Write-Host 'API ya iniciada en http://localhost:8000.' -ForegroundColor Yellow
} else {
    Start-Process cmd.exe -WorkingDirectory $projectRoot -ArgumentList '/k', 'scripts\run-api.cmd' -WindowStyle Normal
    Write-Host 'Backend: http://localhost:8000/docs' -ForegroundColor Green
}

if (Test-NetConnection -ComputerName 127.0.0.1 -Port 5173 -InformationLevel Quiet -WarningAction SilentlyContinue) {
    try { $webResponse = Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 3 } catch {
        throw 'El puerto 5173 está ocupado por otro proceso.'
    }
    if ($webResponse.Content -notmatch '/@vite/client' -or $webResponse.Content -notmatch 'LibrIA') {
        throw 'El puerto 5173 pertenece a otro servicio.'
    }
    Write-Host 'Frontend ya iniciado en http://localhost:5173.' -ForegroundColor Yellow
} else {
    Start-Process powershell.exe -WorkingDirectory $webPath -ArgumentList '-NoExit', '-Command', 'npm run dev'
    Write-Host 'Frontend: http://localhost:5173' -ForegroundColor Green
}

if ($DemoPosts) {
    Start-Process powershell.exe -WorkingDirectory $backendPath -ArgumentList '-NoExit', '-Command', "& '$python' -m scripts.generate_posts --interval 20" -WindowStyle Normal
    Write-Host 'Generador de posts demo iniciado.' -ForegroundColor Yellow
}
