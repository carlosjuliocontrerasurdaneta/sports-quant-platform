@echo off
REM SQP - Validacion OUT-OF-SAMPLE mensual del ROI realizado con parametros
REM congelados. Descubre solo las ligas con odds capturadas (data/odds/), elige
REM parametros usando UNICAMENTE el periodo de train y mide ROI en el periodo de
REM test posterior; compara contra full_history (ratings.yaml) y family_default.
REM Vigila que los parametros sigan generalizando (no overfit). No gasta cuota de
REM API: trabaja sobre datos ya almacenados.
setlocal
cd /d %~dp0
set PYTHONPATH=src
REM Interprete fijo (auditoria 2026-07-24, M-5): bajo el Programador de tareas
REM el PATH puede resolver otro Python. Fallback a "python" si la ruta no existe.
if not defined SQP_PYTHON set "SQP_PYTHON=C:\Users\Richard\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%SQP_PYTHON%" set "SQP_PYTHON=python"

if not exist logs mkdir logs

echo === SQP - VALIDACION OOS MENSUAL (%DATE% %TIME%) ===
call scripts\rotate_log.cmd logs\validate_oos.log
echo === SQP - VALIDACION OOS MENSUAL (%DATE% %TIME%) === >> logs\validate_oos.log
"%SQP_PYTHON%" scripts\validate_oos.py >> logs\validate_oos.log 2>&1
if errorlevel 1 goto :error

REM Marcador modelo-vs-mercado y escalera de min_edge (2026-08-25). Responde si
REM batimos al mercado y si el edge declarado tiene valor realizado. Solo lee
REM datos guardados: no gasta cuota ni escribe en data/. BEST-EFFORT a proposito
REM -- es medicion, no validacion, y no debe poder tumbar la corrida mensual.
echo --- Marcador modelo vs mercado --- >> logs\validate_oos.log
"%SQP_PYTHON%" scripts\model_vs_market_report.py >> logs\validate_oos.log 2>&1
if errorlevel 1 echo *** AVISO: el marcador modelo-vs-mercado fallo (no bloqueante) *** >> logs\validate_oos.log

echo === DONE ===
endlocal
goto :eof

:error
echo.
echo *** ERROR EN LA VALIDACION OOS ***
endlocal
exit /b 1
