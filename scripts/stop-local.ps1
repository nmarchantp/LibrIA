[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$processes = @(Get-CimInstance Win32_Process)
# Identifica ejecutables de este proyecto y luego incluye sus procesos hijos.
$targets = @($processes | Where-Object {
    $_.Name -match '^(node|python|pythonw)\.exe$' -and
    $_.CommandLine -and
    $_.CommandLine.IndexOf($projectRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0
})
$targetIds = [System.Collections.Generic.HashSet[int]]::new()
foreach ($target in $targets) { [void]$targetIds.Add([int]$target.ProcessId) }
do {
    $added = $false
    foreach ($process in $processes) {
        if ($targetIds.Contains([int]$process.ParentProcessId) -and $process.ProcessId -ne $PID) {
            if ($targetIds.Add([int]$process.ProcessId)) { $added = $true }
        }
    }
} while ($added)
if ($targetIds.Count -eq 0) {
    Write-Host 'No hay procesos de LibrIA en ejecución.'
    return
}
# Detiene primero los lanzadores para que no vuelvan a iniciar a sus hijos.
foreach ($targetId in $targetIds) {
    Stop-Process -Id $targetId -Force -ErrorAction SilentlyContinue
}
Write-Host 'Procesos de LibrIA detenidos.' -ForegroundColor Green
