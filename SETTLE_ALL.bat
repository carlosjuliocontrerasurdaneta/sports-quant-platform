@echo off
REM SQP - Liquidacion MULTI-LIGA + auditoria de ROI realizado.
REM Idempotente: re-ejecutar es seguro. Pensado para correr cada manana,
REM despues de que terminen los partidos del dia anterior.
REM
REM ORDEN IMPORTANTE: ejecutar ANTES que RUN_DIARIO_ALL.bat cada dia. El run
REM diario SOBRESCRIBE data\predictions\candidates_*.csv; un pick no liquidado
REM antes de esa sobrescritura se pierde. Cronograma: SETTLE 09:00 -> RUN 10:00.
setlocal
cd /d %~dp0
set PYTHONPATH=src
set ODDS_API_REGIONS=us

if not exist logs mkdir logs

echo === SQP - SETTLE ALL + AUDITORIA (%DATE% %TIME%) ===
call scripts\rotate_log.cmd logs\settle_all.log
echo === SQP - SETTLE ALL + AUDITORIA (%DATE% %TIME%) === >> logs\settle_all.log
python scripts\settle_all.py --days-from 2 >> logs\settle_all.log 2>&1
if errorlevel 1 goto :error

echo === DONE ===
endlocal
goto :eof

:error
echo.
echo *** ERROR EN LA LIQUIDACION ***
endlocal
exit /b 1
