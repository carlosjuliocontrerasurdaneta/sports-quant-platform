# Reintento acotado de la tarea diaria (auditoria audit-2026-10-18, AUD-005;
# autorizado por el operador el 2026-10-19).
#
# El 17-10 SQP_Diario_Completo_Cdev no llego a arrancar (0x8007045B: reinicio de
# Windows Update a las 11:59) y se perdio el dia. La tarea tenia RestartCount=0.
# Esto fija RestartCount=3 y RestartInterval=15 min. Por que es seguro relanzar:
#   - un fallo de LANZAMIENTO no ha hecho ninguna llamada;
#   - si el BAT fallo a mitad, las cuotas se leen de la cache de disco
#     (ODDS_CACHE_TTL_SECONDS, 6 h por defecto: un reintento a los 15 min no
#     gasta creditos, salvo que .env lo baje), la liquidacion es idempotente y
#     el stream servido deduplica por dia de run.
# El vigilante independiente (scripts/check_daily_launch.py desde
# CAPTURE_CLOSE.bat) sigue avisando si aun asi el dia se pierde.
#
# Uso (una vez): powershell -NoProfile -ExecutionPolicy Bypass -File scripts\set_daily_retry.ps1
#   -WhatIf: solo muestra. -Revert: vuelve a RestartCount=0.
# Cambiar los ajustes de una tarea S4U exige un proceso ELEVADO: se relanza solo
# con UAC, como set_tasks_unattended.ps1. Sale con 1 si la tarea no queda como
# se pide (se verifica el resultado, no la ausencia de error).
param([switch]$WhatIf, [switch]$Revert)

$ErrorActionPreference = 'Stop'
$tarea = 'SQP_Diario_Completo_Cdev'
$count = if ($Revert) { 0 } else { 3 }
$interval = 'PT15M'

$esAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $esAdmin -and -not $WhatIf) {
    $argv = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'))
    if ($Revert) { $argv += '-Revert' }
    Write-Output '[info] Sin elevacion: se relanza como administrador (acepta el UAC).'
    try {
        $p = Start-Process -FilePath 'powershell.exe' -ArgumentList $argv -Verb RunAs -Wait -PassThru
    } catch {
        Write-Output ("[ERROR] no se pudo elevar (UAC cancelado?): {0}" -f $_.Exception.Message)
        exit 1
    }
    $r = Get-ScheduledTask -TaskName $tarea
    Write-Output ("[info] proceso elevado: codigo {0}. {1}: RestartCount={2}; RestartInterval={3}" -f $p.ExitCode, $tarea, $r.Settings.RestartCount, $r.Settings.RestartInterval)
    exit $p.ExitCode
}

try {
    $t = Get-ScheduledTask -TaskName $tarea -ErrorAction Stop
    if ($WhatIf) {
        Write-Output ("[whatif] {0}: RestartCount {1} -> {2}; RestartInterval {3} -> {4}" -f $tarea, $t.Settings.RestartCount, $count, $t.Settings.RestartInterval, $interval)
        exit 0
    }
    $s = $t.Settings
    $s.RestartCount = $count
    $s.RestartInterval = $interval
    Set-ScheduledTask -TaskName $tarea -Settings $s -ErrorAction Stop | Out-Null
    $r = Get-ScheduledTask -TaskName $tarea -ErrorAction Stop
    if ([int]$r.Settings.RestartCount -ne $count) {
        throw ("RestartCount quedo en {0} (esperado {1})" -f $r.Settings.RestartCount, $count)
    }
    Write-Output ("[ok] {0}: RestartCount={1}; RestartInterval={2}; LogonType={3}" -f $tarea, $r.Settings.RestartCount, $r.Settings.RestartInterval, $r.Principal.LogonType)
    exit 0
} catch {
    Write-Output ("[ERROR] {0}: {1}" -f $tarea, $_.Exception.Message)
    exit 1
}
