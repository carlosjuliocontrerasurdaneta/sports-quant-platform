# Abre el dashboard diario (data\predictions\report_latest.html) en el navegador.
#
# Disenado para correr como tarea interactiva del Programador (SQP_Dashboard_Cdev):
# DIARIO_COMPLETO.bat la dispara al terminar (schtasks /Run) y un trigger "al
# iniciar sesion" cubre el caso de que el run de las 12:00 ocurra sin nadie
# logueado. Abrir el navegador desde la propia tarea del run crasheaba con
# 0xC000013A (sin escritorio); por eso la apertura vive en una tarea aparte
# que el Programador lanza en la sesion interactiva del usuario.
#
# Sin -Force abre UNA vez al dia (marcador logs\dashboard_shown_YYYYMMDD.flag)
# para no reabrirlo en cada logon.
#
# SI EL REPORTE NO ES DE HOY, SE ABRE IGUAL Y SE AVISA (AUD-HIGH-002, auditoria
# integral 2026-09-13). Hasta entonces este script hacia `exit 0` con "El
# reporte no es de hoy; se omite", es decir: se callaba EXACTAMENTE el dia en
# que el run diario no habia ocurrido. Medido: sin run el 07, 08, 10 y 11 de
# septiembre de 2026 (4 de 7 dias) y nadie recibio una senal, porque el
# health_check solo corre DENTRO de DIARIO_COMPLETO.bat -- el proceso cuya
# ausencia habia que detectar. Ahora: (1) se ejecuta scripts\health_check.py al
# iniciar sesion, independiente del orquestador (su `pipeline_liveness` pasa el
# estado a ERROR si no hay artefacto reciente); (2) si el reporte no es de hoy
# o la salud es ERROR, se muestra un aviso modal y se abre el reporte viejo, que
# es mejor senal que ninguna. Ambas cosas son best-effort: un fallo aqui nunca
# impide abrir el tablero.
param([switch]$Force)
# Solo para PRUEBAS (tests/test_open_dashboard.py): con SQP_DASHBOARD_NO_UI=1 no
# se abre navegador ni cuadro modal; todo lo demas (liveness, aviso en salida,
# marcador) se ejecuta igual, que es lo que la prueba comprueba.
$sinUI = [bool]$env:SQP_DASHBOARD_NO_UI

$root = Split-Path -Parent $PSScriptRoot
$report = Join-Path $root 'data\predictions\report_latest.html'
$logsDir = Join-Path $root 'logs'
$marker = Join-Path $logsDir ("dashboard_shown_{0}.flag" -f (Get-Date -Format 'yyyyMMdd'))

if (-not (Test-Path $report)) {
    Write-Output "[open_dashboard] No existe $report; nada que abrir."
    exit 0
}

if (-not $Force) {
    if (Test-Path $marker) {
        Write-Output '[open_dashboard] Dashboard ya mostrado hoy; se omite.'
        exit 0
    }
}
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }

# (1) Liveness independiente del orquestador: health_check.py escribe
# data\output\pipeline_health.json y sale con 1 si el estado es ERROR (incluye
# "el pipeline diario NO ha generado nada en 1.5 dias"). Mismo interprete fijo
# que los .bat (SQP_PYTHON), con caida a "python" del PATH.
$py = $env:SQP_PYTHON
if (-not $py -or -not (Test-Path $py)) { $py = 'C:\Users\Richard\AppData\Local\Programs\Python\Python314\python.exe' }
if (-not (Test-Path $py)) { $py = 'python' }
$healthLog = Join-Path $logsDir 'open_dashboard.log'
$healthRc = $null
try {
    $env:PYTHONPATH = 'src'
    Push-Location $root
    & $py 'scripts\health_check.py' 2>&1 | Out-File -Append -FilePath $healthLog -Encoding utf8
    $healthRc = $LASTEXITCODE
} catch {
    "[open_dashboard] health_check.py no pudo ejecutarse: $_" | Out-File -Append -FilePath $healthLog -Encoding utf8
} finally {
    Pop-Location
}

# (2) El reporte de un dia anterior se abre IGUAL, con aviso: un tablero viejo
# a la vista es una senal; ninguno, un silencio identico al de un sistema sano.
$lastWrite = (Get-Item $report).LastWriteTime
$isToday = $lastWrite.Date -eq (Get-Date).Date
if ((-not $isToday) -or ($healthRc -eq 1)) {
    if (-not $isToday) {
        $razon = "El reporte diario NO es de hoy (ultimo: $($lastWrite.ToString('yyyy-MM-dd HH:mm'))): el run diario no se ha ejecutado hoy."
    } else {
        $razon = "health_check.py reporta ERROR (ver data\output\pipeline_health.json)."
    }
    Write-Output "[open_dashboard] AVISO: $razon Se abre el reporte igualmente."
    try {
        if ($sinUI) { throw 'SQP_DASHBOARD_NO_UI' }
        Add-Type -AssemblyName System.Windows.Forms
        $texto = "$razon`n`nRevisa la tarea SQP_Diario_Completo_Cdev y logs\diario_completo.log.`nSe abre el ultimo reporte disponible."
        [System.Windows.Forms.MessageBox]::Show($texto, 'SQP - sin run diario', 'OK', 'Warning') | Out-Null
    } catch {
        Write-Output "[open_dashboard] (sin cuadro de aviso: $_)"
    }
}

if (-not $sinUI) { Start-Process $report }
Set-Content -Path $marker -Value (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') -Encoding utf8

# Limpieza de marcadores viejos (>7 dias) para no acumular flags en logs\.
Get-ChildItem $logsDir -Filter 'dashboard_shown_*.flag' -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
    Remove-Item -Force -ErrorAction SilentlyContinue

Write-Output "[open_dashboard] Dashboard abierto: $report"
