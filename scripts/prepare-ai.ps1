[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$backendPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'apps\backend'
$python = Join-Path $backendPath '.venv\Scripts\python.exe'
$envPath = Join-Path $backendPath '.env'
if (-not (Test-Path -LiteralPath $envPath)) { throw 'Ejecuta setup.cmd primero.' }

# Agrega solo variables nuevas; conserva credenciales y decisiones locales.
$content = Get-Content -LiteralPath $envPath -Raw
$missing = @()
foreach ($line in Get-Content -LiteralPath (Join-Path $backendPath '.env.example')) {
    if ($line -match '^([A-Z][A-Z0-9_]*)=(.*)$') {
        $key = $Matches[1]
        if ($content -notmatch "(?m)^\s*$key\s*=") { $missing += $line }
    }
}
if ($missing.Count) { Add-Content -LiteralPath $envPath -Value ("`n" + ($missing -join "`n")) -Encoding utf8 }

# Usa el mismo lector de configuracion que la API, incluyendo variables del entorno.
Push-Location $backendPath
try {
    $settingsJson = & $python -c 'import json; from app.core.config import get_settings; s=get_settings(); print(json.dumps(dict(url=s.ollama_base_url, model=s.ai_model)))'
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo leer la configuracion de IA.' }
    $settings = $settingsJson | ConvertFrom-Json
} finally { Pop-Location }

function Find-Ollama {
    $command = Get-Command ollama.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $local = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    if (Test-Path -LiteralPath $local) { return $local }
}

Write-Host 'Preparando Ollama y el modelo de IA local...' -ForegroundColor Cyan
$ollama = Find-Ollama
if (-not $ollama) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw 'Instala Ollama desde https://ollama.com/download/windows y vuelve a ejecutar update.cmd.'
    }
    & winget.exe install --id Ollama.Ollama --exact --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo instalar Ollama. Instala desde https://ollama.com/download/windows y reintenta.' }
    $ollama = Find-Ollama
    if (-not $ollama) { throw 'Vuelve a abrir la terminal y ejecuta update.cmd para encontrar Ollama.' }
}

$baseUrl = $settings.url.TrimEnd('/')
function Read-Models {
    Invoke-RestMethod -Uri "$baseUrl/api/tags" -TimeoutSec 3
}
try { $models = Read-Models } catch {
    $previousHost = $env:OLLAMA_HOST
    try {
        $env:OLLAMA_HOST = $baseUrl
        Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden | Out-Null
    } finally { $env:OLLAMA_HOST = $previousHost }
    $models = $null
    for ($attempt = 0; $attempt -lt 15; $attempt++) {
        Start-Sleep -Seconds 1
        try { $models = Read-Models; break } catch { }
    }
    if ($null -eq $models) { throw "Ollama no responde en $baseUrl. Revisa su inicio y vuelve a ejecutar update.cmd." }
}

$model = $settings.model
$modelTag = if ($model -match ':') { $model } else { "${model}:latest" }
if (@($models.models | Where-Object { $_.name -eq $modelTag -or $_.model -eq $modelTag }).Count -eq 0) {
    Write-Host "Descargando $model (requiere Internet y espacio en disco)..." -ForegroundColor Cyan
    $previousHost = $env:OLLAMA_HOST
    try {
        $env:OLLAMA_HOST = $baseUrl
        & $ollama pull $model
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo descargar el modelo. Revisa la conexion y el espacio disponible y reintenta update.cmd.' }
    } finally { $env:OLLAMA_HOST = $previousHost }
    $models = Read-Models
    if (@($models.models | Where-Object { $_.name -eq $modelTag -or $_.model -eq $modelTag }).Count -eq 0) {
        throw 'Ollama no informa el modelo descargado. Revisa AI_MODEL en apps/backend/.env.'
    }
}
Write-Host "IA local lista: $model en $baseUrl" -ForegroundColor Green
