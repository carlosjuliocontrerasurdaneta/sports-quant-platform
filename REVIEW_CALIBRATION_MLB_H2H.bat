@echo off
REM Revision de calibracion MLB h2h (seguimiento 2026-06-28; actualizado 2026-07-01
REM al flujo staging/promocion). Ver docs\CALIBRATION-2026-06-21.md.
REM
REM FLUJO ACTUAL (train != promote):
REM   1) train_calibration.py entrena sobre las apuestas liquidadas reales
REM      (data\bets\settled_*.csv, ancladas a la apertura) y deja CANDIDATOS en
REM      data\models\staging\. NUNCA toca el registro live.
REM   2) promote_calibration.py SIN flags = dry-run: muestra diff staging vs live
REM      y preview del candidato sobre una grilla de probabilidades.
REM   3) Decision HUMANA: si el candidato mejora el ECE/Brier OOS y el preview no
REM      es degenerado (p.ej. favoritos empujados a 0.9+), promover con
REM      promote_calibration.py --keys mlb_h2h (o --yes para todos). Si no,
REM      no hacer nada: el live queda no-op.
REM
REM Nota: --rebuild solo aplica con --source backtest (pick_history); el default
REM 'settled' no lo usa. El run diario ya reconstruye pick_history para el dashboard.
setlocal
cd /d %~dp0
set PYTHONPATH=src
if not exist logs mkdir logs

echo === REVISION CALIBRACION MLB h2h (%DATE% %TIME%) === >> logs\calibration_review.log
python scripts\train_calibration.py >> logs\calibration_review.log 2>&1
if errorlevel 1 goto :error

echo --- promote_calibration DRY-RUN (staging vs live) --- >> logs\calibration_review.log
python scripts\promote_calibration.py >> logs\calibration_review.log 2>&1
if errorlevel 1 goto :error

REM Abrir el dashboard para inspeccionar la pestana Auditoria (ROI realizado por mercado).
REM Solo en sesion interactiva: bajo el Programador de tareas (SESSIONNAME vacio)
REM se omite porque abrir el navegador puede terminar el proceso (cf. RUN_DIARIO).
REM El reporte HTML se escribe igual; abrelo manualmente desde el bookmark.
if defined SESSIONNAME start "" "data\predictions\report_latest.html"

echo Revision generada (candidatos en data\models\staging\; live SIN tocar).
echo Log: logs\calibration_review.log
echo Para promover tras revisar: python scripts\promote_calibration.py --keys mlb_h2h
echo Guia de decision: docs\CALIBRATION-2026-06-21.md
endlocal
goto :eof

:error
echo.
echo *** ERROR EN LA REVISION DE CALIBRACION. Revisa logs\calibration_review.log. ***
endlocal
exit /b 1
