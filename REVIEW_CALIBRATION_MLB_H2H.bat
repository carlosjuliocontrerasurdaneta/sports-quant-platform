@echo off
REM Revision de calibracion MLB h2h (seguimiento 2026-06-28).
REM Ver docs\CALIBRATION-2026-06-21.md. Reconstruye el historial, reentrena los
REM calibradores por (liga, mercado) reportando el ECE OOS antes/despues, y abre
REM el reporte para revisar la pestana Auditoria (mlb / h2h).
REM
REM Decision (manual): si el ROI realizado de MLB h2h contradice el edge estimado
REM o el ECE OOS empeora -> borrar data\models\mlb_h2h_calibration_iso.joblib y
REM _beta.joblib (ese mercado queda sin calibrar, no-op). Si mejora -> mantener.
setlocal
cd /d %~dp0
set PYTHONPATH=src
if not exist logs mkdir logs

echo === REVISION CALIBRACION MLB h2h (%DATE% %TIME%) === >> logs\calibration_review.log
REM --rebuild reconstruye data\processed\pick_history.csv desde el backtest antes de calibrar.
python scripts\train_calibration.py --rebuild >> logs\calibration_review.log 2>&1

REM Abrir el dashboard para inspeccionar la pestana Auditoria (ROI realizado por mercado).
start "" "data\predictions\report_latest.html"

echo Revision generada. Log: logs\calibration_review.log
echo Guia de decision: docs\CALIBRATION-2026-06-21.md
endlocal
