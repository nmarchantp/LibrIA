[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendPath = Join-Path $projectRoot 'apps\backend'
$pythonPath = Join-Path $backendPath '.venv\Scripts\python.exe'
$taskName = 'LibrIA-ETL-Diario'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Configura el entorno Python antes de programar el ETL.' }
if ((Get-TimeZone).Id -ne 'Pacific SA Standard Time') {
    throw 'La tarea de Windows requiere la zona horaria de Santiago (Pacific SA Standard Time). El programador de FastAPI sigue usando America/Santiago.'
}

$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask -and ($existingTask.Actions.Execute -ne $pythonPath -or $existingTask.Actions.Arguments -ne '-m scripts.run_etl')) {
    throw 'Ya existe una tarea con este nombre y otra acción; no se reemplaza.'
}
$accountName = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument '-m scripts.run_etl' -WorkingDirectory $backendPath
$trigger = New-ScheduledTaskTrigger -Daily -At '00:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
# No almacena contraseñas. Disponible mientras la cuenta tiene sesión iniciada.
$principal = New-ScheduledTaskPrincipal -UserId $accountName -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Cierre diario LibrIA: carga única del día anterior en analytics, a medianoche de Santiago.' -Force | Select-Object TaskName, State
Get-ScheduledTaskInfo -TaskName $taskName | Select-Object NextRunTime, LastTaskResult
