# Pasa las tareas del pipeline a "ejecutar aunque el usuario no haya iniciado
# sesion" (LogonType S4U: sin contrasena almacenada) y activa WakeToRun.
#
# AUD-HIGH-002 (auditoria integral 2026-09-13): las 5 tareas SQP_* estaban en
# "Solo interactivo" y el run diario no se ejecuto 4 de 7 dias (07, 08, 10 y
# 11 de septiembre) sin dejar rastro. S4U ejecuta la tarea como el mismo
# usuario, sin escritorio y sin credenciales de red (HTTPS a las APIs funciona;
# lo que no funciona es abrir un navegador, y por eso SQP_Dashboard_Cdev se
# queda como esta: DIARIO_COMPLETO.bat ya la dispara con `schtasks /Run` cuando
# no hay SESSIONNAME).
#
# Uso (una vez, desde una consola del usuario):
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\set_tasks_unattended.ps1
#   powershell ... -File scripts\set_tasks_unattended.ps1 -WhatIf   # solo muestra
#
# Reversion: el mismo script con -Revert (vuelve a Interactive).
param([switch]$WhatIf, [switch]$Revert)

$tareas = 'SQP_Diario_Completo_Cdev', 'SQP_Capture_Close_Cdev', 'SQP_Backfill_Cdev', 'SQP_Validate_OOS_Cdev'
$logon = if ($Revert) { 'Interactive' } else { 'S4U' }
foreach ($n in $tareas) {
    $t = Get-ScheduledTask -TaskName $n -ErrorAction Stop
    $antes = $t.Principal.LogonType
    if ($WhatIf) {
        Write-Output ("[whatif] {0}: {1} -> {2}; WakeToRun -> {3}" -f $n, $antes, $logon, (-not $Revert))
        continue
    }
    $principal = New-ScheduledTaskPrincipal -UserId $t.Principal.UserId -LogonType $logon -RunLevel $t.Principal.RunLevel
    $s = $t.Settings
    $s.WakeToRun = -not $Revert
    Set-ScheduledTask -TaskName $n -Principal $principal -Settings $s | Out-Null
    $r = Get-ScheduledTask -TaskName $n
    $i = Get-ScheduledTaskInfo -TaskName $n
    Write-Output ("{0}: {1} -> {2}; WakeToRun={3}; estado={4}; proxima={5}" -f $n, $antes, $r.Principal.LogonType, $r.Settings.WakeToRun, $r.State, $i.NextRunTime)
}
