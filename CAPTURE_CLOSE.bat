@echo off
REM SQP - Captura de linea de cierre. Horaria. Solo gasta cuota en ligas con
REM picks abiertos cuyo partido arranca en <120 min (guard interno + tope diario
REM de creditos). Anade un segundo snapshot de cuotas para que el CLV sea medible.
setlocal
cd /d %~dp0
set PYTHONPATH=src
set ODDS_API_REGIONS=us,eu,uk,au

if not exist logs mkdir logs

call scripts\rotate_log.cmd logs\capture_close.log
echo === SQP - CAPTURA CIERRE (%DATE% %TIME%) === >> logs\capture_close.log
python scripts\capture_closing_odds.py >> logs\capture_close.log 2>&1
if errorlevel 1 goto :error

endlocal
goto :eof

:error
echo.
echo *** ERROR EN LA CAPTURA DE CIERRE. Revisa logs\capture_close.log. ***
endlocal
exit /b 1
