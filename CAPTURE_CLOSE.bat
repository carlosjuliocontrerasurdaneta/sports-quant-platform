@echo off
REM SQP - Captura de linea de cierre. Horaria. Solo gasta cuota en ligas con
REM picks abiertos cuyo partido arranca en <120 min (guard interno + tope diario
REM de creditos). Anade un segundo snapshot de cuotas para que el CLV sea medible.
setlocal
cd /d %~dp0
set PYTHONPATH=src
REM Interprete fijo (auditoria 2026-07-24, M-5): bajo el Programador de tareas
REM el PATH puede resolver otro Python. Fallback a "python" si la ruta no existe.
if not defined SQP_PYTHON set "SQP_PYTHON=C:\Users\Richard\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%SQP_PYTHON%" set "SQP_PYTHON=python"
set ODDS_API_REGIONS=us,us2,uk,eu,au

if not exist logs mkdir logs

call scripts\rotate_log.cmd logs\capture_close.log
echo === SQP - CAPTURA CIERRE (%DATE% %TIME%) === >> logs\capture_close.log
"%SQP_PYTHON%" scripts\capture_closing_odds.py >> logs\capture_close.log 2>&1
if errorlevel 1 goto :error

endlocal
goto :eof

:error
echo.
echo *** ERROR EN LA CAPTURA DE CIERRE. Revisa logs\capture_close.log. ***
endlocal
exit /b 1
