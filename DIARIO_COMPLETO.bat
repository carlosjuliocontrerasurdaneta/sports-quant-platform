@echo off
REM SQP - Orquestador diario COMPLETO: encadena liquidacion + run en el orden
REM correcto para que el run NUNCA sobrescriba picks sin liquidar.
REM
REM ORDEN GARANTIZADO:
REM   1) SETTLE_ALL.bat  (liquida los picks del dia anterior + auditoria)
REM   2) RUN_DIARIO_ALL.bat  (genera los picks del dia y sobrescribe candidates_*)
REM
REM Si la liquidacion falla, ABORTA antes del run para no perder picks. Como
REM respaldo, el pipeline ahora archiva data\predictions\archive\ antes de
REM sobrescribir, asi que un pick sin liquidar siempre queda recuperable.
REM
REM Usar ESTE bat en el programador de tareas en vez de los dos por separado.
setlocal
cd /d %~dp0
REM Mismo interprete fijo que los BAT que encadena (auditoria 2026-07-24, M-5).
if not defined SQP_PYTHON set "SQP_PYTHON=C:\Users\Richard\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%SQP_PYTHON%" set "SQP_PYTHON=python"

echo === SQP - DIARIO COMPLETO (%DATE% %TIME%) ===

echo [1/2] Liquidando picks del dia anterior...
call "%~dp0SETTLE_ALL.bat"
if errorlevel 1 goto :error_settle

echo [2/2] Ejecutando run diario multi-liga...
call "%~dp0RUN_DIARIO_ALL.bat"
if errorlevel 1 goto :error_run

REM Run correcto: limpia el centinela para que el health check deje de
REM reportar ERROR (auditoria 2026-07-29, S-1).
"%SQP_PYTHON%" scripts\run_status.py --clear

echo === DIARIO COMPLETO: OK ===

REM Flujo terminado: abre el dashboard automaticamente.
REM - Sesion interactiva (SESSIONNAME definido): abre directo via open_dashboard.ps1 -Force.
REM - Bajo el Programador de tareas (sin escritorio): abrir el navegador desde ESTE
REM   proceso terminaba con 0xC000013A, asi que se dispara la tarea interactiva
REM   SQP_Dashboard_Cdev (scripts\register_dashboard_task.ps1), que el Programador
REM   lanza en la sesion del usuario. Si nadie esta logueado, el trigger de logon
REM   de esa tarea abre el dashboard al iniciar sesion (gateado por frescura+marcador).
if defined SESSIONNAME (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\open_dashboard.ps1" -Force
) else (
    schtasks /Run /TN SQP_Dashboard_Cdev >nul 2>&1 || echo [INFO] No se pudo disparar SQP_Dashboard_Cdev; el dashboard abrira al iniciar sesion.
)

endlocal
goto :eof

:error_settle
echo.
"%SQP_PYTHON%" scripts\run_status.py --fail --stage settle --exit-code 1
echo *** ERROR EN LA LIQUIDACION: se ABORTA el run diario para no perder picks. ***
echo *** Revisa logs\settle_all.log, corrige y vuelve a ejecutar este bat.     ***
endlocal
exit /b 1

:error_run
echo.
"%SQP_PYTHON%" scripts\run_status.py --fail --stage run --exit-code 1
echo *** ERROR EN EL RUN DIARIO (la liquidacion si termino). ***
echo *** Revisa logs\run_diario.log.                          ***
endlocal
exit /b 1
