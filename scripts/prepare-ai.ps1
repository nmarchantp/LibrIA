[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$backendPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'apps\backend'
$python = Join-Path $backendPath '.venv\Scripts\python.exe'
$envPath = Join-Path $backendPath '.env'
if (-not (Test-Path -LiteralPath $envPath)) { throw 'Ejecuta setup.cmd primero.' }

# Agrega variables nuevas sin reemplazar decisiones ni credenciales locales.
$content = Get-Content -LiteralPath $envPath -Raw
$missing = @()
foreach ($line in Get-Content -LiteralPath (Join-Path $backendPath '.env.example')) {
    if ($line -match '^([A-Z][A-Z0-9_]*)=(.*)$') {
        $key = $Matches[1]
        if ($content -notmatch "(?m)^\s*$key\s*=") { $missing += $line }
    }
}
if ($missing.Count) { Add-Content -LiteralPath $envPath -Value ("`n" + ($missing -join "`n")) -Encoding utf8 }

Push-Location $backendPath
try {
    $summary = & $python -c 'from app.core.config import get_settings; s=get_settings(); print(s.ai_provider); print(s.gemini_model); print(s.gemini_worker_enabled); print(s.gemini_paid_service_confirmed); print(s.gemini_free_test_mode)'
    if ($LASTEXITCODE -ne 0) { throw 'La configuración de IA no es válida.' }
} finally { Pop-Location }

Write-Host "Configuración Gemini validada ($summary). No se realizan llamadas al proveedor." -ForegroundColor Green
