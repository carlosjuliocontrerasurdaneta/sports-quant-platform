# Registra (o re-registra) la tarea SQP_Dashboard_Cdev en el Programador de tareas.
#
# La tarea es INTERACTIVA (LogonType Interactive): el Programador la ejecuta en
# la sesion del usuario logueado, asi el navegador abre en su escritorio sin el
# crash 0xC000013A que ocurria al abrirlo desde la tarea no interactiva del run.
# Triggers:
#   - Al iniciar sesion (delay 1 min): si el run de las 11:00 corrio sin sesion,
#     el dashboard abre al loguearse (open_dashboard.ps1 gatea por frescura+marcador).
#   - Bajo demanda: DIARIO_COMPLETO.bat la dispara con schtasks /Run al terminar.
# Idempotente: re-correr reemplaza la definicion existente.

$taskName = 'SQP_Dashboard_Cdev'
$scriptPath = Join-Path $PSScriptRoot 'open_dashboard.ps1'

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath`""

$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$logonTrigger.Delay = 'PT1M'

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $logonTrigger `
    -Principal $principal -Settings $settings -Force | Out-Null

Write-Output "[register_dashboard_task] Tarea '$taskName' registrada (accion: $scriptPath)."
