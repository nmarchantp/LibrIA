[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendPath = Join-Path $projectRoot 'apps\backend'
$webPath = Join-Path $projectRoot 'apps\web'

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Assert-LastCommand([string]$Description) {
    if ($LASTEXITCODE -ne 0) { throw "$Description falló con código $LASTEXITCODE." }
}

function New-RandomSecret([int]$Length = 40) {
    $alphabet = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    -join (1..$Length | ForEach-Object { $alphabet[(Get-Random -Maximum $alphabet.Length)] })
}

function Find-Python {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue)
    )
    $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
}

function Find-Psql {
    $command = Get-Command psql.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\psql.exe' -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -ExpandProperty FullName -First 1
}

Write-Step 'Comprobando herramientas requeridas'
$python = Find-Python
if (-not $python) {
    throw 'Python 3.12 no está instalado. Instala: winget install --id Python.Python.3.12 --exact'
}
if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) {
    throw 'Node.js no está instalado. Instala: winget install --id OpenJS.NodeJS.LTS --exact'
}
$psql = Find-Psql
if (-not $psql) {
    throw 'PostgreSQL 17 no está instalado. Instala: winget install --id PostgreSQL.PostgreSQL.17 --exact'
}

Write-Step 'Configurando PostgreSQL'
$secureAdminPassword = Read-Host 'Contraseña del usuario postgres definida durante la instalación' -AsSecureString
$adminPassword = [System.Net.NetworkCredential]::new('', $secureAdminPassword).Password
$appPassword = New-RandomSecret 32
$env:PGPASSWORD = $adminPassword
try {
    $roleExists = & $psql -U postgres -h localhost -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='libria'"
    if ($roleExists -eq '1') {
        & $psql -U postgres -h localhost -d postgres -v ON_ERROR_STOP=1 -c "ALTER ROLE libria WITH LOGIN PASSWORD '$appPassword';" | Out-Null
        Assert-LastCommand 'La actualización del usuario PostgreSQL'
    } else {
        & $psql -U postgres -h localhost -d postgres -v ON_ERROR_STOP=1 -c "CREATE ROLE libria WITH LOGIN PASSWORD '$appPassword';" | Out-Null
        Assert-LastCommand 'La creación del usuario PostgreSQL'
    }
    $databaseExists = & $psql -U postgres -h localhost -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='libria'"
    if ($databaseExists -ne '1') {
        & $psql -U postgres -h localhost -d postgres -v ON_ERROR_STOP=1 -c 'CREATE DATABASE libria OWNER libria;' | Out-Null
        Assert-LastCommand 'La creación de la base PostgreSQL'
    }
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    $adminPassword = $null
}

Write-Step 'Creando configuración local segura'
$jwtSecret = New-RandomSecret 64
$environment = @"
APP_NAME=LibrIA API
APP_ENV=development
API_PREFIX=/api
DATABASE_URL=postgresql+psycopg://libria:$appPassword@localhost:5432/libria
FRONTEND_ORIGINS=http://localhost:5173
JWT_SECRET=$jwtSecret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
"@
Set-Content -LiteralPath (Join-Path $backendPath '.env') -Value $environment -Encoding utf8

Write-Step 'Instalando backend Python'
$venvPython = Join-Path $backendPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) { & $python -m venv (Join-Path $backendPath '.venv') }
& $venvPython -m pip install --disable-pip-version-check -r (Join-Path $backendPath 'requirements.txt')
Assert-LastCommand 'La instalación de dependencias Python'
Push-Location $backendPath
try {
    & $venvPython -m alembic upgrade head
    Assert-LastCommand 'La migración de base de datos'
} finally { Pop-Location }

Write-Step 'Instalando frontend JavaScript'
Push-Location $webPath
try {
    # npm ci garantiza un clon exacto; npm install permite repetir el setup sin
    # borrar binarios que podrían estar siendo observados por el editor.
    if (Test-Path -LiteralPath (Join-Path $webPath 'node_modules')) { npm install } else { npm ci }
    Assert-LastCommand 'La instalación del frontend'
} finally { Pop-Location }

Write-Host "`nInstalación terminada correctamente." -ForegroundColor Green
Write-Host 'Ejecuta: .\scripts\run-local.ps1'
