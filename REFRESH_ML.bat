@echo off
REM SQP - Mantenimiento ML semanal. NO toca la generacion de picks (eso sigue en
REM RUN_DIARIO_ALL.bat por la via de simulacion). Aqui solo se mantienen frescos
REM los datasets de features y los modelos ML, y se reporta la comparacion
REM sim-vs-ML (evidencia para decidir el blend) + salud del pipeline.
REM Correr semanal, despues de un backfill de resultados reciente.
setlocal
cd /d %~dp0
set PYTHONPATH=src

if not exist logs mkdir logs

echo === SQP - REFRESH ML (%DATE% %TIME%) ===
echo === SQP - REFRESH ML (%DATE% %TIME%) === >> logs\refresh_ml.log
python scripts\build_features.py >> logs\refresh_ml.log 2>&1
if errorlevel 1 goto :error
python scripts\train_models.py --oos >> logs\refresh_ml.log 2>&1
if errorlevel 1 goto :error
python scripts\compare_models.py >> logs\refresh_ml.log 2>&1
if errorlevel 1 goto :error
python scripts\health_check.py >> logs\refresh_ml.log 2>&1
if errorlevel 1 goto :error

echo === DONE ===
endlocal
goto :eof

:error
echo.
echo *** ERROR EN REFRESH ML. Revisa logs\refresh_ml.log. ***
endlocal
exit /b 1
