@echo off
REM SQP - Orquestador diario COMPLETO: encadena liquidacion + run en el orden
REM correcto para que el run NUNCA sobrescriba picks sin liquidar.
REM
REM ORDEN GARANTIZADO:
REM   1) SETTLE_ALL.bat  (liquida los picks del dia anterior + auditoria)
REM   2) RUN_DIARIO_ALL.bat  (genera los picks del dia y sobrescribe candidates_*)
REM
REM Si la liquidacion falla, ABORTA antes del run para no perder picks. Como
REM respaldo, el pipeline ahora archiva data\predictions\archive\ antes de
REM sobrescribir, asi que un pick sin liquidar siempre queda recuperable.
REM
REM Usar ESTE bat en el programador de tareas en vez de los dos por separado.
setlocal
cd /d %~dp0

echo === SQP - DIARIO COMPLETO (%DATE% %TIME%) ===

echo [1/2] Liquidando picks del dia anterior...
call "%~dp0SETTLE_ALL.bat"
if errorlevel 1 goto :error_settle

echo [2/2] Ejecutando run diario multi-liga...
call "%~dp0RUN_DIARIO_ALL.bat"
if errorlevel 1 goto :error_run

echo === DIARIO COMPLETO: OK ===

REM Flujo terminado: abre el dashboard de inmediato (SIEMPRE). Va al final, ya
REM escritos picks + reporte + report_latest.html, para que cualquier problema al
REM lanzar el navegador no afecte el trabajo hecho. AVISO: bajo el Programador de
REM tareas (sin escritorio) abrir el navegador puede terminar el proceso con
REM 0xC000013A; el trabajo ya quedo completo de todos modos.
start "" "%~dp0data\predictions\report_latest.html"

endlocal
goto :eof

:error_settle
echo.
echo *** ERROR EN LA LIQUIDACION: se ABORTA el run diario para no perder picks. ***
echo *** Revisa logs\settle_all.log, corrige y vuelve a ejecutar este bat.     ***
endlocal
exit /b 1

:error_run
echo.
echo *** ERROR EN EL RUN DIARIO (la liquidacion si termino). ***
echo *** Revisa logs\run_diario.log.                          ***
endlocal
exit /b 1
