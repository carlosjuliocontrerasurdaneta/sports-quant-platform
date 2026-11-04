# Espera a que el arbol de codigo quede limpio antes del flujo diario (AUD-002,
# ronda audit-2026-11-03).
#
# El guard de arbol limpio de DIARIO_COMPLETO.bat (KI-036) abortaba de inmediato:
# el 2026-11-03 una sesion de desarrollo dejo el portero NHL sin commitear a las
# 12:00 y el dia entero se perdio. Crear una tarea de reintento exige proceso
# ELEVADO (las SQP_* corren en S4U), asi que se espera dentro del propio BAT con
# el mismo patron que scripts\wait_for_network.ps1: se re-evalua el guard cada
# IntervalSeconds hasta MaxMinutes y solo entonces se aborta. Esperar aqui no
# cuesta nada: todavia no se ha tocado ningun dato.
#
# Mismo ambito que el guard: solo codigo que produccion EJECUTA
# (src, scripts, configs, *.bat). Solo lectura: nunca modifica el repositorio.
#
# Salida: 0 si el arbol esta limpio (o no se puede comprobar: falla abierto,
# igual que el guard), 1 si sigue sucio tras agotar el plazo.
param(
    [double]$MaxMinutes = 180,
    [int]$IntervalSeconds = 900
)

function Get-ArbolSucio {
    # Devuelve las lineas sucias, o $null si git no pudo responder.
    $lineas = & git status --porcelain -- src scripts configs '*.bat' 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    return @($lineas | Where-Object { $_ })
}

function Write-Log([string]$msg) {
    Write-Output ("{0} [arbol] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg)
}

$limite = (Get-Date).AddMinutes($MaxMinutes)
$avisado = $false
while ($true) {
    $sucio = Get-ArbolSucio
    if ($null -eq $sucio) {
        Write-Log "git no pudo comprobar el arbol; se continua (falla abierto)."
        exit 0
    }
    if ($sucio.Count -eq 0) {
        if ($avisado) { Write-Log "arbol limpio; se continua." }
        exit 0
    }
    if ((Get-Date) -ge $limite) {
        Write-Log "arbol SUCIO ($($sucio.Count) fichero(s)) tras $MaxMinutes min de espera."
        exit 1
    }
    if (-not $avisado) {
        Write-Log "arbol SUCIO ($($sucio.Count) fichero(s)); se re-evalua cada $IntervalSeconds s hasta $($limite.ToString('HH:mm'))."
        $avisado = $true
    }
    Start-Sleep -Seconds ([Math]::Min($IntervalSeconds, [Math]::Max(1, [int]($limite - (Get-Date)).TotalSeconds)))
}
