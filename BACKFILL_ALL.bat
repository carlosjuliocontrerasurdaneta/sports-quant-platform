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

if not exist logs mkdir logs

echo === SQP - BACKFILL SEMANAL (%DATE% %TIME%) ===
call scripts\rotate_log.cmd logs\backfill.log
echo === SQP - BACKFILL SEMANAL (%DATE% %TIME%) === >> logs\backfill.log
python scripts\backfill_results.py --days 14 --leagues mlb nba wnba ncaab wncaab nfl ncaaf nhl epl laliga bundesliga seriea ligue1 ucl ligamx mls brasileirao chile uwcl >> logs\backfill.log 2>&1
if errorlevel 1 goto :error

echo === DONE ===
endlocal
goto :eof

:error
echo.
echo *** ERROR EN EL BACKFILL ***
endlocal
exit /b 1
