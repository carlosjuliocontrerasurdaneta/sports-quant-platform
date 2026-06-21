@echo off
REM SQP - Run diario MULTI-LIGA: todas las ligas en temporada que el presupuesto
REM de cuota permita (guard automatico), + reporte consolidado de picks.
REM La actualizacion incremental de ratings ocurre dentro del pipeline (recent
REM scores). Para SEMBRAR una liga nueva, corre antes scripts\backfill_results.py.
REM
REM ORDEN IMPORTANTE: corre SETTLE_ALL.bat ANTES que este script cada dia. Este
REM run SOBRESCRIBE data\predictions\candidates_*.csv, asi que los picks del dia
REM anterior deben liquidarse primero o se pierden. Cronograma: SETTLE 09:00 ->
REM RUN 10:00.
setlocal
cd /d %~dp0
set PYTHONPATH=src
REM Plan de pago 20,000 creditos/mes; el guard de presupuesto raciona la cuota real.
set ODDS_API_REGIONS=us,eu,uk,au

if not exist logs mkdir logs

echo === SQP - RUN DIARIO MULTI-LIGA (%DATE% %TIME%) ===
echo === SQP - RUN DIARIO MULTI-LIGA (%DATE% %TIME%) === >> logs\run_diario.log
REM --open-dashboard se omite a proposito: bajo el Programador de tareas la
REM apertura del navegador terminaba el proceso con 0xC000013A. El reporte HTML
REM se escribe igual; abrir data\predictions\report_latest.html como bookmark.
python scripts\run_all.py --mode live >> logs\run_diario.log 2>&1
if errorlevel 1 goto :error

echo === DONE ===
endlocal
goto :eof

:error
echo.
echo *** ERROR EN LA EJECUCION ***
endlocal
exit /b 1
