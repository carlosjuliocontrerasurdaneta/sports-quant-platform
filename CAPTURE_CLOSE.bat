@echo off
REM SQP - Captura de linea de cierre. CADA 30 MIN (SQP_Capture_Close_Cdev,
REM Repetition.Interval = PT30M); este comentario decia "horaria" y llevaba al
REM menos desde julio sin coincidir con el disparador (AUD-LOW-003). Solo gasta cuota en ligas con
REM picks abiertos cuyo partido arranca en <120 min (guard interno + tope diario
REM de creditos). Anade un segundo snapshot de cuotas para que el CLV sea medible.
setlocal
cd /d %~dp0
set PYTHONPATH=src
REM Interprete fijo (auditoria 2026-07-24, M-5): bajo el Programador de tareas
REM el PATH puede resolver otro Python. Fallback a "python" si la ruta no existe.
if not defined SQP_PYTHON set "SQP_PYTHON=C:\Users\Richard\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%SQP_PYTHON%" echo [AVISO] SQP_PYTHON no existe en la ruta fijada; se cae a "python" del PATH, que puede ser otra version y sin las dependencias pineadas de requirements.lock.
if not exist "%SQP_PYTHON%" set "SQP_PYTHON=python"
set ODDS_API_REGIONS=us,us2,uk,eu,au

if not exist logs mkdir logs

call scripts\rotate_log.cmd logs\capture_close.log
echo === SQP - CAPTURA CIERRE (%DATE% %TIME%) === >> logs\capture_close.log
"%SQP_PYTHON%" scripts\capture_closing_odds.py >> logs\capture_close.log 2>&1
REM El rc se guarda ANTES de los porteros (seguimiento de AUD-004, 2026-10-16):
REM con el salto inmediato a :error, cualquier rc!=0 de la captura -- desde hoy
REM tambien el fallo parcial de ligas -- se llevaba por delante la captura de
REM porteros de esa pasada, que no depende de ella.
set "CAPTURE_RC=%ERRORLEVEL%"

REM Porteros probables NHL (2026-09-26): DESPUES de la captura de cierre para
REM no retrasarla; log propio; no bloqueante (nunca salta a :error).
call scripts\rotate_log.cmd logs\goalie_probables.log
"%SQP_PYTHON%" scripts\capture_goalie_probables_nhl.py --source-run capture >> logs\goalie_probables.log 2>&1
if %ERRORLEVEL% neq 0 echo [AVISO] captura de porteros probables NHL fallo (no bloqueante) >> logs\goalie_probables.log

REM Vigilancia del lanzamiento del run diario (AUD-005, ronda audit-2026-10-18):
REM el 17-10 la tarea de las 12:00 no arranco (0x8007045B, reinicio de Windows
REM Update) y nada lo dijo, porque los avisos viven DENTRO del run que falto.
REM No bloqueante y no relanza nada: solo escribe/borra el centinela.
"%SQP_PYTHON%" scripts\check_daily_launch.py >> logs\capture_close.log 2>&1

if not "%CAPTURE_RC%"=="0" goto :error

REM Captura correcta: limpia SOLO esta etapa (corre cada 30 min, asi que se
REM auto-recupera en la siguiente pasada buena).
"%SQP_PYTHON%" scripts\run_status.py --clear --only-stage capture_close

endlocal
goto :eof

:error
echo.
REM AUD-MED-003 (2026-09-06): sin centinela, un fallo de la captura era invisible.
REM Importa mas de lo que parece: esta es la que produce el segundo snapshot de
REM cuotas, y sin el el CLV no es medible -- el gate de CLV se quedaria sin
REM evidencia nueva indefinidamente, denegando por defecto (que es seguro) pero
REM sin que nadie supiera por que.
"%SQP_PYTHON%" scripts\run_status.py --fail --stage capture_close --exit-code 1
echo *** ERROR EN LA CAPTURA DE CIERRE. Revisa logs\capture_close.log. ***
endlocal
exit /b 1
