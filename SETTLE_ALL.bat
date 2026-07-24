@echo off
REM SQP - Liquidacion MULTI-LIGA + auditoria de ROI realizado.
REM Idempotente: re-ejecutar es seguro. Pensado para correr cada manana,
REM despues de que terminen los partidos del dia anterior.
REM
REM ORDEN IMPORTANTE: ejecutar ANTES que RUN_DIARIO_ALL.bat cada dia. El run
REM diario SOBRESCRIBE data\predictions\candidates_*.csv; un pick no liquidado
REM antes de esa sobrescritura se pierde. En produccion NO se agenda este bat
REM por separado: DIARIO_COMPLETO.bat (tarea SQP_Diario_Completo_Cdev, diaria
REM 11:00) encadena SETTLE -> RUN en ese orden.
setlocal
cd /d %~dp0
set PYTHONPATH=src
REM Interprete fijo (auditoria 2026-07-24, M-5): bajo el Programador de tareas
REM el PATH puede resolver otro Python. Fallback a "python" si la ruta no existe.
if not defined SQP_PYTHON set "SQP_PYTHON=C:\Users\Richard\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%SQP_PYTHON%" set "SQP_PYTHON=python"
set ODDS_API_REGIONS=us

if not exist logs mkdir logs

echo === SQP - SETTLE ALL + AUDITORIA (%DATE% %TIME%) ===
call scripts\rotate_log.cmd logs\settle_all.log
echo === SQP - SETTLE ALL + AUDITORIA (%DATE% %TIME%) === >> logs\settle_all.log
"%SQP_PYTHON%" scripts\settle_all.py --days-from 2 >> logs\settle_all.log 2>&1
if errorlevel 1 goto :error

echo === DONE ===
endlocal
goto :eof

:error
echo.
echo *** ERROR EN LA LIQUIDACION ***
endlocal
exit /b 1
