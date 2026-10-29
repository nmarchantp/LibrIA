[CmdletBinding()]
param([switch]$AllowMainDatabaseMigration)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendPath = Join-Path $projectRoot 'apps\backend'
$webPath = Join-Path $projectRoot 'apps\web'
$envPath = Join-Path $backendPath '.env'

function Write-Step([string]$Message) { Write-Host "`n==> $Message" -ForegroundColor Cyan }
function Assert-LastCommand([string]$Description) { if ($LASTEXITCODE -ne 0) { throw "$Description falló con código $LASTEXITCODE." } }
function Find-Python {
    $candidates = @((Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'), (Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1))
    $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}
function Find-PgDump {
    $c = Get-Command pg_dump.exe -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\pg_dump.exe' -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -ExpandProperty FullName -First 1
}
function Get-EnvMap([string]$Path) {
    $map = @{}
    foreach ($line in Get-Content -LiteralPath $Path -ErrorAction Stop) {
        if ($line -match '^([A-Z][A-Z0-9_]*)=(.*)$') { $map[$Matches[1]] = $Matches[2] }
    }
    return $map
}
function Set-EnvValue([string]$Path, [string]$Key, [string]$Value) {
    $content = if (Test-Path $Path) { @(Get-Content -LiteralPath $Path) } else { @() }
    $escaped = [regex]::Escape($Key)
    $found = $false
    $content = $content | ForEach-Object {
        if ($_ -match "^\s*$escaped\s*=.*") { $found = $true; "$Key=$Value" } else { $_ }
    }
    if (-not $found) { $content += "$Key=$Value" }
    Set-Content -LiteralPath $Path -Value $content -Encoding utf8
}
function New-RandomSecret([int]$Length = 64) {
    $bytes = New-Object byte[] $Length
    $rng = New-Object Security.Cryptography.RNGCryptoServiceProvider
    $rng.GetBytes($bytes)
    $rng.Dispose()
    return (-join ($bytes | ForEach-Object { '{0:x2}' -f $_ }))
}

Write-Step 'Comprobando herramientas requeridas'
$python = Find-Python
if (-not $python) { throw 'Python 3.12 no está instalado. Instala: winget install --id Python.Python.3.12 --exact' }
if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) { throw 'Node.js no está instalado. Instala: winget install --id OpenJS.NodeJS.LTS --exact' }

Write-Step 'Preservando configuración local existente'
if (-not (Test-Path -LiteralPath $envPath)) { throw 'No existe apps/backend/.env. Copia apps/backend/.env.example y configura allí tu entorno.' }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Copy-Item -LiteralPath $envPath -Destination "$envPath.backup-$stamp" -Force
$envMap = Get-EnvMap $envPath

if ([string]::IsNullOrWhiteSpace($envMap['DATABASE_URL'])) {
    Write-Host 'DATABASE_URL está vacío. Configuraré únicamente la conexión aislada que indiques; no asumiré libria ni PostgreSQL principal.' -ForegroundColor Yellow
    $databaseHost = Read-Host 'Host PostgreSQL (Enter para localhost)'
    if ([string]::IsNullOrWhiteSpace($databaseHost)) { $databaseHost = 'localhost' }
    $databasePort = Read-Host 'Puerto PostgreSQL (Enter para 5432)'
    if ([string]::IsNullOrWhiteSpace($databasePort)) { $databasePort = '5432' }
    $databaseName = Read-Host 'Nombre de la base aislada'
    if ([string]::IsNullOrWhiteSpace($databaseName)) { throw 'No se configurará una base sin un nombre explícito.' }
    $databaseUser = Read-Host 'Usuario PostgreSQL'
    if ([string]::IsNullOrWhiteSpace($databaseUser)) { throw 'No se configurará una base sin usuario explícito.' }
    $securePassword = Read-Host 'Contraseña PostgreSQL' -AsSecureString
    $databasePassword = [Net.NetworkCredential]::new('', $securePassword).Password
    $encodedPassword = [Uri]::EscapeDataString($databasePassword)
    Set-EnvValue $envPath 'DATABASE_URL' "postgresql+psycopg://$databaseUser`:$encodedPassword@$databaseHost`:$databasePort/$databaseName"
    $databasePassword = $null
    $envMap = Get-EnvMap $envPath
}

if ([string]::IsNullOrWhiteSpace($envMap['JWT_SECRET'])) { Set-EnvValue $envPath 'JWT_SECRET' (New-RandomSecret 64) }
if ([string]::IsNullOrWhiteSpace($envMap['LIBRIA_DEMO_PASSWORD'])) { Set-EnvValue $envPath 'LIBRIA_DEMO_PASSWORD' (New-RandomSecret 24) }
foreach ($line in Get-Content -LiteralPath (Join-Path $backendPath '.env.example')) {
    if ($line -match '^([A-Z][A-Z0-9_]*)=(.*)$') {
        $current = Get-EnvMap $envPath
        if (-not $current.ContainsKey($Matches[1])) { Set-EnvValue $envPath $Matches[1] $Matches[2] }
    }
}

Write-Step 'Configurando entorno Python'
$venvPython = Join-Path $backendPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) { & $python -m venv (Join-Path $backendPath '.venv'); Assert-LastCommand 'La creación del entorno Python' }
& $venvPython -m pip install --disable-pip-version-check -r (Join-Path $backendPath 'requirements.txt'); Assert-LastCommand 'La instalación de dependencias Python'
& $venvPython -m pip check; Assert-LastCommand 'La comprobación de dependencias Python'

Write-Step 'Configurando frontend'
Push-Location $webPath
try { if (Test-Path -LiteralPath (Join-Path $webPath 'node_modules')) { npm install } else { npm ci }; Assert-LastCommand 'La instalación de dependencias frontend' } finally { Pop-Location }
$webEnv = Join-Path $webPath '.env'
if (-not (Test-Path -LiteralPath $webEnv)) { Copy-Item -LiteralPath (Join-Path $webPath '.env.example') -Destination $webEnv }

Write-Step 'Validando PostgreSQL y revisión de Alembic (sin migrar)'
Push-Location $backendPath
try {
    & $venvPython -c 'from app.core.database import engine; c=engine.connect(); c.close()'
    Assert-LastCommand 'La conexión PostgreSQL'
    & $venvPython -m alembic current
    & $venvPython -m alembic heads
} finally { Pop-Location }

if ($AllowMainDatabaseMigration) {
    $confirmation = Read-Host 'Confirmación: escriba MIGRAR-POR-EXPLICITO para autorizar una migración sobre la base configurada'
    if ($confirmation -ne 'MIGRAR-POR-EXPLICITO') { throw 'Migración cancelada: no se recibió confirmación explícita.' }
    $pgDump = Find-PgDump
    if (-not $pgDump) { throw 'pg_dump no está disponible. No se iniciará la migración.' }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backupPath = Join-Path $projectRoot "backups\libria-$stamp.sql"
    New-Item -ItemType Directory -Path (Split-Path $backupPath) -Force | Out-Null

    Push-Location $backendPath
    try {
        $connectionJson = & $venvPython -c "import json; from app.core.database import engine; u=engine.url; print(json.dumps(dict(host=u.host or 'localhost', port=u.port or 5432, username=u.username or '', database=u.database or '')))"
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($connectionJson)) {
            throw 'No se pudo resolver la conexión PostgreSQL.'
        }
        try { $connection = $connectionJson | ConvertFrom-Json } catch {
            throw 'La conexión PostgreSQL no entregó metadatos válidos.'
        }
        $hostName = $connection.host
        $portNumber = $connection.port
        $userName = $connection.username
        $databaseName = $connection.database
        if ([string]::IsNullOrWhiteSpace($hostName) -or
            [string]::IsNullOrWhiteSpace([string]$portNumber) -or
            [string]::IsNullOrWhiteSpace($userName) -or
            [string]::IsNullOrWhiteSpace($databaseName)) {
            throw 'La conexión PostgreSQL está incompleta; revisa DATABASE_URL.'
        }
        $env:PGPASSWORD = (Get-EnvMap $envPath)['DATABASE_PASSWORD']
        if (-not $env:PGPASSWORD) {
            $passwordUrl = $envMap['DATABASE_URL']
            if ($passwordUrl -match '://[^:]+:([^@]+)@') { $env:PGPASSWORD = [Uri]::UnescapeDataString($Matches[1]) }
        }
        Write-Host 'Creando respaldo antes de migrar...' -ForegroundColor Yellow
        $dumpArgs = @("--host=$hostName", "--port=$portNumber", "--username=$userName", '--format=plain', "--file=$backupPath", "--dbname=$databaseName")
        & $pgDump @dumpArgs
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $backupPath) -or (Get-Item $backupPath).Length -le 0) { throw 'El respaldo falló o está vacío. No se migrará la base.' }
        & $venvPython -m alembic upgrade head
        Assert-LastCommand 'La migración explícita'
        & $venvPython -m scripts.seed_default_admin
        Assert-LastCommand 'La carga inicial del administrador y su biblioteca'
    } finally {
        Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
        Pop-Location
    }
} else {
    Write-Host 'Migraciones: no ejecutadas por defecto. No se aplicará alembic upgrade sin -AllowMainDatabaseMigration y confirmación explícita.' -ForegroundColor Yellow
}

& (Join-Path $PSScriptRoot 'prepare-ai.ps1')
Write-Host "`nSetup completo. .env local preservado y respaldado. No hubo llamadas Gemini ni cambios destructivos sobre bases de datos." -ForegroundColor Green
