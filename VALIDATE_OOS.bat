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

if not exist logs mkdir logs

echo === SQP - VALIDACION OOS MENSUAL (%DATE% %TIME%) ===
call scripts\rotate_log.cmd logs\validate_oos.log
echo === SQP - VALIDACION OOS MENSUAL (%DATE% %TIME%) === >> logs\validate_oos.log
python scripts\validate_oos.py >> logs\validate_oos.log 2>&1
if errorlevel 1 goto :error

echo === DONE ===
endlocal
goto :eof

:error
echo.
echo *** ERROR EN LA VALIDACION OOS ***
endlocal
exit /b 1
