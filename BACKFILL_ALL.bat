@echo off
REM SQP - Backfill semanal de resultados historicos (ESPN / MLB Stats API).
REM Persiste los scores en data/historical/ para que las ratings no queden
REM limitadas a la ventana de 3 dias de The Odds API (auditoria 2026-06, I-1).
REM Idempotente: el store deduplica por (date,home,away,game_id); el solape de
REM 14 dias con cadencia semanal evita huecos. Las ligas fuera de temporada
REM devuelven 0 resultados (inofensivo).
setlocal
cd /d %~dp0
set PYTHONPATH=src
REM Interprete fijo (auditoria 2026-07-24, M-5): bajo el Programador de tareas
REM el PATH puede resolver otro Python. Fallback a "python" si la ruta no existe.
if not defined SQP_PYTHON set "SQP_PYTHON=C:\Users\Richard\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%SQP_PYTHON%" set "SQP_PYTHON=python"

if not exist logs mkdir logs

echo === SQP - BACKFILL SEMANAL (%DATE% %TIME%) ===
call scripts\rotate_log.cmd logs\backfill.log
echo === SQP - BACKFILL SEMANAL (%DATE% %TIME%) === >> logs\backfill.log
"%SQP_PYTHON%" scripts\backfill_results.py --days 14 --leagues mlb nba wnba ncaab wncaab nfl ncaaf nhl epl laliga bundesliga seriea ligue1 ucl ligamx mls brasileirao chile uwcl >> logs\backfill.log 2>&1
if errorlevel 1 goto :error
REM Tenis: store por tour (results_atp/wta), no por torneo; sin esto los Elo de
REM tenis corren con forma vieja (causa #1 de la sobreconfianza del 2026-07-04).
"%SQP_PYTHON%" scripts\backfill_tennis_results.py --tours atp wta --days 14 >> logs\backfill.log 2>&1
if errorlevel 1 goto :error

REM Purga semanal de artefactos regenerables (>90 dias): archive/, clv_*.md,
REM .closing_credits_*. Best-effort a proposito: un fallo de la purga no debe
REM marcar el backfill como fallido (por eso no hay chequeo de errorlevel).
"%SQP_PYTHON%" scripts\purge_artifacts.py >> logs\backfill.log 2>&1

echo === DONE ===
endlocal
goto :eof

:error
echo.
echo *** ERROR EN EL BACKFILL ***
endlocal
exit /b 1
