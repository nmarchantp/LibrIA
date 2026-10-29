[CmdletBinding()]
param([ValidateSet('local', 'docker')][string]$Target)

$ErrorActionPreference = 'Stop'
$envPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'apps\backend\.env'
if (-not (Test-Path -LiteralPath $envPath)) { throw 'No existe apps/backend/.env.' }

if (-not $Target) {
    Write-Host '1. URL guardada en DATABASE_URL_LOCAL' -ForegroundColor Cyan
    Write-Host '2. URL guardada en DATABASE_URL_DOCKER' -ForegroundColor Cyan
    $choice = Read-Host 'Selecciona 1 o 2'
    $Target = if ($choice -eq '2') { 'docker' } else { 'local' }
}

$profileKey = if ($Target -eq 'docker') { 'DATABASE_URL_DOCKER' } else { 'DATABASE_URL_LOCAL' }
$content = @(Get-Content -LiteralPath $envPath)
$profileValue = $null
foreach ($line in $content) {
    if ($line -match "^\s*$profileKey\s*=\s*(.+)$") { $profileValue = $Matches[1].Trim(); break }
}
if ([string]::IsNullOrWhiteSpace($profileValue)) {
    throw "No existe $profileKey en .env. Agrégala manualmente con el host, puerto y base reales de ese equipo."
}
if ($profileValue -notmatch '^postgresql\+psycopg://') {
    throw "$profileKey no contiene una URL PostgreSQL SQLAlchemy válida."
}

$replaced = $false
$updated = foreach ($line in $content) {
    if ($line -match '^\s*DATABASE_URL\s*=') {
        $replaced = $true
        "DATABASE_URL=$profileValue"
    } else { $line }
}
if (-not $replaced) { $updated += "DATABASE_URL=$profileValue" }
Set-Content -LiteralPath $envPath -Value $updated -Encoding utf8
Write-Host "Configuración activa: $Target. No se asumió puerto, nombre de base ni contraseña." -ForegroundColor Green
