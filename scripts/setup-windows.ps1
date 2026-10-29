[CmdletBinding()]
param([switch]$AllowMainDatabaseMigration)

# Wrapper de compatibilidad. Toda instalación usa el procedimiento conservador;
# este archivo ya no crea roles/bases, sobrescribe .env, carga el catálogo ni
# migra sin respaldo y confirmación explícita.
$safeSetup = Join-Path $PSScriptRoot 'setup-windows-safe.ps1'
if (-not (Test-Path -LiteralPath $safeSetup)) { throw 'No se encontró setup-windows-safe.ps1.' }
& $safeSetup -AllowMainDatabaseMigration:$AllowMainDatabaseMigration
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
