# Abre el dashboard diario (data\predictions\report_latest.html) en el navegador.
#
# Disenado para correr como tarea interactiva del Programador (SQP_Dashboard_Cdev):
# DIARIO_COMPLETO.bat la dispara al terminar (schtasks /Run) y un trigger "al
# iniciar sesion" cubre el caso de que el run de las 11:00 ocurra sin nadie
# logueado. Abrir el navegador desde la propia tarea del run crasheaba con
# 0xC000013A (sin escritorio); por eso la apertura vive en una tarea aparte
# que el Programador lanza en la sesion interactiva del usuario.
#
# Sin -Force solo abre si el reporte es de HOY y aun no se mostro hoy
# (marcador logs\dashboard_shown_YYYYMMDD.flag) para no reabrirlo en cada logon.
param([switch]$Force)

$root = Split-Path -Parent $PSScriptRoot
$report = Join-Path $root 'data\predictions\report_latest.html'
$logsDir = Join-Path $root 'logs'
$marker = Join-Path $logsDir ("dashboard_shown_{0}.flag" -f (Get-Date -Format 'yyyyMMdd'))

if (-not (Test-Path $report)) {
    Write-Output "[open_dashboard] No existe $report; nada que abrir."
    exit 0
}

if (-not $Force) {
    $isToday = (Get-Item $report).LastWriteTime.Date -eq (Get-Date).Date
    if (-not $isToday) {
        Write-Output '[open_dashboard] El reporte no es de hoy; se omite.'
        exit 0
    }
    if (Test-Path $marker) {
        Write-Output '[open_dashboard] Dashboard ya mostrado hoy; se omite.'
        exit 0
    }
}

Start-Process $report
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }
Set-Content -Path $marker -Value (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') -Encoding utf8

# Limpieza de marcadores viejos (>7 dias) para no acumular flags en logs\.
Get-ChildItem $logsDir -Filter 'dashboard_shown_*.flag' -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
    Remove-Item -Force -ErrorAction SilentlyContinue

Write-Output "[open_dashboard] Dashboard abierto: $report"
