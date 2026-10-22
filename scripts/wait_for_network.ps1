# Espera a que haya salida a Internet antes del flujo diario (KI-076, 2026-10-22).
#
# El 21-10 y el 22-10 la tarea de las 12:00 arranco con el Wi-Fi caido
# (NetworkProfile 10001 a las 08:42 y 11:17; reconexion 19:10 y 13:36): cada
# liga agoto sus reintentos contra The Odds API durante ~40 min, la liquidacion
# aborto y el dia quedo sin picks. Esperar aqui no cuesta nada: todavia no se ha
# tocado ningun dato.
#
# Sonda: conexion TCP a api.the-odds-api.com:443. No hace ninguna peticion HTTP,
# asi que no gasta creditos de la API.
#
# Salida: 0 si hay red (en cuanto la hay), 1 si se agota la espera.
param(
    [int]$MaxMinutes = 480,
    [int]$IntervalSeconds = 120,
    [string]$HostName = 'api.the-odds-api.com',
    [int]$Port = 443,
    [int]$ConnectTimeoutMs = 5000
)

function Test-Salida {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $intento = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $intento.AsyncWaitHandle.WaitOne($ConnectTimeoutMs)) { return $false }
        $client.EndConnect($intento)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Write-Log([string]$msg) {
    Write-Output ("{0} [red] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg)
}

$limite = (Get-Date).AddMinutes($MaxMinutes)
$avisado = $false
while ($true) {
    if (Test-Salida) {
        if ($avisado) { Write-Log "conexion a ${HostName}:$Port recuperada; se continua." }
        exit 0
    }
    if ((Get-Date) -ge $limite) {
        Write-Log "sin conexion a ${HostName}:$Port tras $MaxMinutes min de espera."
        exit 1
    }
    if (-not $avisado) {
        Write-Log "sin conexion a ${HostName}:$Port; se reintenta cada $IntervalSeconds s hasta $($limite.ToString('HH:mm'))."
        $avisado = $true
    }
    Start-Sleep -Seconds $IntervalSeconds
}
