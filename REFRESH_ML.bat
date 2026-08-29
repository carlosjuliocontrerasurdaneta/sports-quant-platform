@echo off
REM SQP - Mantenimiento ML semanal. NO toca la generacion de picks (eso sigue en
REM RUN_DIARIO_ALL.bat por la via de simulacion). Aqui solo se mantienen frescos
REM los datasets de features y los modelos ML, y se reporta la comparacion
REM sim-vs-ML (evidencia para decidir el blend) + salud del pipeline.
REM
REM MANUAL desde el 2026-08-29: ya NO hay tarea programada. La semanal
REM `SQP_Refresh_ML_Cdev` (lunes 09:45) se retiro por orden del operador tras la
REM auditoria integral (AUD-LOW-003): la inferencia ML no tiene ningun llamador
REM en src/ ni en scripts/ -- `predict_moneyline`/`predict_total` solo los usan
REM sus tests --, asi que lo que se entrenaba aqui no influia en ningun pick.
REM Su ultimo resultado fue ademas 0xC000013A (terminacion anomala).
REM
REM Correr a mano cuando se quiera reevaluar el blend, despues de un backfill de
REM resultados reciente. La comparacion sim-vs-ML que produce es la evidencia
REM para decidir si conectarlo. Definicion de la tarea retirada, por si hay que
REM restaurarla: docs\ops\SQP_Refresh_ML_Cdev.task.xml
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
