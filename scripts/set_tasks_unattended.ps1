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
# HISTORIAL DEL PROGRAMADOR (AUD-004, auditoria integral 2026-09-18). El log
# `Microsoft-Windows-TaskScheduler/Operational` estaba DESHABILITADO: cuando una
# tarea no llega a lanzarse (maquina apagada, disparador que no salta), no queda
# ningun rastro fuera del BAT -- y el BAT no arranco. Los dias 11, 15 y 16-09
# quedaron sin causa diagnosticable por eso. Habilitarlo exige una consola
# ELEVADA (no basta con que la cuenta sea admin; ver .claude/memory):
#   wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true
# Comprobar:  (Get-WinEvent -ListLog 'Microsoft-Windows-TaskScheduler/Operational').IsEnabled
# `scripts\health_check.py` avisa mientras siga apagado (bloque `scheduled_tasks`
# de data\output\pipeline_health.json, que ademas expone LastRunTime/LastTaskResult
# de las 5 tareas como rastro independiente del BAT).
#
# Reversion: el mismo script con -Revert (vuelve a Interactive).
# Sale con 1 si CUALQUIER tarea no queda en el estado pedido (revision cruzada
# 2026-09-13: un `Set-ScheduledTask` denegado era un error no terminante y el
# script terminaba en verde con las tareas sin tocar).
param([switch]$WhatIf, [switch]$Revert)

$ErrorActionPreference = 'Stop'

# AUTO-ELEVACION. Cambiar el LogonType de una tarea a S4U exige un proceso
# elevado aunque la cuenta sea administradora: sin UAC, Windows responde
# "Acceso denegado" en las cuatro (observado el 2026-09-13 desde una consola
# normal). Si no estamos elevados, se relanza el mismo script con -Verb RunAs
# (salta el UAC), se espera y se devuelve SU codigo de salida. -WhatIf no
# necesita elevacion.
$esAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $esAdmin -and -not $WhatIf) {
    $args = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'))
    if ($Revert) { $args += '-Revert' }
    Write-Output '[info] Sin elevacion: se relanza como administrador (acepta el UAC).'
    try {
        $p = Start-Process -FilePath 'powershell.exe' -ArgumentList $args -Verb RunAs -Wait -PassThru
    } catch {
        Write-Output ("[ERROR] no se pudo elevar (UAC cancelado?): {0}" -f $_.Exception.Message)
        exit 1
    }
    Write-Output ("[info] proceso elevado terminado con codigo {0}. Comprueba el estado:" -f $p.ExitCode)
    foreach ($n in 'SQP_Diario_Completo_Cdev', 'SQP_Capture_Close_Cdev', 'SQP_Backfill_Cdev', 'SQP_Validate_OOS_Cdev') {
        $r = Get-ScheduledTask -TaskName $n
        Write-Output ("  {0}: LogonType={1}; WakeToRun={2}" -f $n, $r.Principal.LogonType, $r.Settings.WakeToRun)
    }
    exit $p.ExitCode
}
$tareas = 'SQP_Diario_Completo_Cdev', 'SQP_Capture_Close_Cdev', 'SQP_Backfill_Cdev', 'SQP_Validate_OOS_Cdev'
$logon = if ($Revert) { 'Interactive' } else { 'S4U' }
$wake = -not $Revert
$fallos = 0
foreach ($n in $tareas) {
    try {
        $t = Get-ScheduledTask -TaskName $n -ErrorAction Stop
        $antes = $t.Principal.LogonType
        if ($WhatIf) {
            Write-Output ("[whatif] {0}: {1} -> {2}; WakeToRun -> {3}" -f $n, $antes, $logon, $wake)
            continue
        }
        $principal = New-ScheduledTaskPrincipal -UserId $t.Principal.UserId -LogonType $logon -RunLevel $t.Principal.RunLevel
        $s = $t.Settings
        $s.WakeToRun = $wake
        Set-ScheduledTask -TaskName $n -Principal $principal -Settings $s -ErrorAction Stop | Out-Null
        # Se verifica el RESULTADO, no la ausencia de error: es lo que exige
        # el resto del repositorio a todo control.
        $r = Get-ScheduledTask -TaskName $n -ErrorAction Stop
        if ([string]$r.Principal.LogonType -ne $logon -or [bool]$r.Settings.WakeToRun -ne $wake) {
            throw ("la tarea quedo en LogonType={0}, WakeToRun={1} (esperado {2}/{3})" -f $r.Principal.LogonType, $r.Settings.WakeToRun, $logon, $wake)
        }
        $i = Get-ScheduledTaskInfo -TaskName $n -ErrorAction Stop
        Write-Output ("{0}: {1} -> {2}; WakeToRun={3}; estado={4}; proxima={5}" -f $n, $antes, $r.Principal.LogonType, $r.Settings.WakeToRun, $r.State, $i.NextRunTime)
    } catch {
        $fallos++
        Write-Output ("[ERROR] {0}: {1}" -f $n, $_.Exception.Message)
    }
}
if ($fallos -gt 0) {
    Write-Output ("[ERROR] {0} tarea(s) NO quedaron en el estado pedido. Nada que celebrar." -f $fallos)
    if ($esAdmin -and -not $WhatIf) { try { Read-Host 'Pulsa Enter para cerrar' | Out-Null } catch {} }
    exit 1
}
if ($esAdmin -and -not $WhatIf) { try { Read-Host 'Hecho. Pulsa Enter para cerrar' | Out-Null } catch {} }
exit 0
