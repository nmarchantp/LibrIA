[CmdletBinding()]
param([switch]$AllowLocalCredentialReset)

$ErrorActionPreference = 'Stop'
$envPath = Join-Path $PSScriptRoot '..\apps\backend\.env'
$envPath = [IO.Path]::GetFullPath($envPath)
$psql = 'C:\Program Files\PostgreSQL\17\bin\psql.exe'

if (-not $AllowLocalCredentialReset) {
    throw 'Operación bloqueada. Usa -AllowLocalCredentialReset solo para restablecer el rol libria local existente.'
}

if (-not (Test-Path -LiteralPath $psql)) {
    throw 'No se encontró PostgreSQL 17 en C:\Program Files\PostgreSQL\17\bin.'
}
if (-not (Test-Path -LiteralPath $envPath)) {
    throw 'No existe apps/backend/.env.'
}

$secureAdminPassword = Read-Host 'Contraseña del usuario postgres definido al instalar PostgreSQL' -AsSecureString
$adminPassword = [Net.NetworkCredential]::new('', $secureAdminPassword).Password
$env:PGPASSWORD = $adminPassword

try {
    $role = & $psql -U postgres -h 127.0.0.1 -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='libria'"
    if ($LASTEXITCODE -ne 0 -or $role.Trim() -ne '1') {
        throw 'No se pudo autenticar como postgres o el rol libria no existe. No se modificó PostgreSQL.'
    }

    $database = & $psql -U postgres -h 127.0.0.1 -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='libria'"
    if ($LASTEXITCODE -ne 0 -or $database.Trim() -ne '1') {
        throw 'La base libria existente no fue encontrada. No se creó ninguna base nueva.'
    }

    $confirmation = Read-Host 'Escriba RESET-CREDENCIALES-LIBRIA para cambiar el rol local existente'
    if ($confirmation -ne 'RESET-CREDENCIALES-LIBRIA') {
        throw 'Operación cancelada; no se modificaron credenciales.'
    }

    $bytes = New-Object byte[] 48
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $random.GetBytes($bytes)
    } finally {
        $random.Dispose()
    }
    $appPassword = [Convert]::ToBase64String($bytes)
    $appPassword = $appPassword.Replace('+', 'A').Replace('/', 'B').Replace('=', 'C')
    $escapedPassword = $appPassword.Replace("'", "''")

    & $psql -U postgres -h 127.0.0.1 -d postgres -v ON_ERROR_STOP=1 `
        -c "ALTER ROLE libria WITH LOGIN PASSWORD '$escapedPassword';" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudo restablecer el rol libria existente.'
    }
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    $adminPassword = $null
}

$content = @(Get-Content -LiteralPath $envPath)
$currentDocker = $null
foreach ($line in $content) {
    if ($line -match '^#?\s*DATABASE_URL_DOCKER=(.*)$') {
        if ($Matches[1] -match '55432/libria_test') {
            $currentDocker = $Matches[1]
        }
    }
    if ($line -match '^DATABASE_URL=(.*)$' -and $Matches[1] -match '55432/libria_test') {
        $currentDocker = $Matches[1]
    }
}

$clean = @()
foreach ($line in $content) {
    if ($line -notmatch '^#?\s*DATABASE_URL(?:_LOCAL|_DOCKER)?=') {
        $clean += $line
    }
}

$clean += '# DATABASE_URL_LOCAL=postgresql+psycopg://libria:****@127.0.0.1:5432/libria'
if (-not [string]::IsNullOrWhiteSpace($currentDocker)) {
    $clean += '# DATABASE_URL_DOCKER=' + $currentDocker
} else {
    $clean += '# DATABASE_URL_DOCKER=postgresql+psycopg://libria_test:****@127.0.0.1:55432/libria_test'
}
$encodedPassword = [Uri]::EscapeDataString($appPassword)
$clean += 'DATABASE_URL=postgresql+psycopg://libria:' + $encodedPassword + '@127.0.0.1:5432/libria'
Set-Content -LiteralPath $envPath -Value $clean -Encoding utf8

$env:PGPASSWORD = $appPassword
try {
    $verified = & $psql -U libria -h 127.0.0.1 -d libria -tAc 'SELECT current_database(), current_user'
    if ($LASTEXITCODE -ne 0 -or $verified.Trim().Length -eq 0) {
        throw 'La contraseña nueva fue aplicada pero la conexión de libria falló.'
    }
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    $appPassword = $null
}

Write-Host 'Restaurada la conexión a la base local existente libria en 127.0.0.1:5432.' -ForegroundColor Green
Write-Host 'No se creó ninguna base ni se ejecutaron migraciones.' -ForegroundColor Yellow
