@echo off
REM SQP - Mantenimiento ML semanal. NO toca la generacion de picks (eso sigue en
REM RUN_DIARIO_ALL.bat por la via de simulacion). Aqui solo se mantienen frescos
REM los datasets de features y los modelos ML, y se reporta la comparacion
REM sim-vs-ML (evidencia para decidir el blend) + salud del pipeline.
REM Correr semanal, despues de un backfill de resultados reciente.
setlocal
cd /d %~dp0
set PYTHONPATH=src
REM Interprete fijo (auditoria 2026-07-24, M-5): bajo el Programador de tareas
REM el PATH puede resolver otro Python. Fallback a "python" si la ruta no existe.
if not defined SQP_PYTHON set "SQP_PYTHON=C:\Users\Richard\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%SQP_PYTHON%" set "SQP_PYTHON=python"

if not exist logs mkdir logs

echo === SQP - REFRESH ML (%DATE% %TIME%) ===
call scripts\rotate_log.cmd logs\refresh_ml.log
echo === SQP - REFRESH ML (%DATE% %TIME%) === >> logs\refresh_ml.log
"%SQP_PYTHON%" scripts\build_features.py >> logs\refresh_ml.log 2>&1
if errorlevel 1 goto :error
"%SQP_PYTHON%" scripts\train_models.py --oos >> logs\refresh_ml.log 2>&1
if errorlevel 1 goto :error
"%SQP_PYTHON%" scripts\compare_models.py >> logs\refresh_ml.log 2>&1
if errorlevel 1 goto :error
"%SQP_PYTHON%" scripts\health_check.py >> logs\refresh_ml.log 2>&1
if errorlevel 1 goto :error

echo === DONE ===
endlocal
goto :eof

:error
echo.
echo *** ERROR EN REFRESH ML. Revisa logs\refresh_ml.log. ***
endlocal
exit /b 1
