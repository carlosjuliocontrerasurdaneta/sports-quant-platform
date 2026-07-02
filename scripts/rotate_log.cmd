@echo off
REM Rotacion simple de logs por tamano (auditoria 2026-07-02, hallazgo B2):
REM   call scripts\rotate_log.cmd logs\run_diario.log
REM Si el log supera 5 MB se mueve a <log>.1 (pisa la generacion anterior),
REM acotando el disco a ~10 MB por log. Por tamano y no por fecha a proposito:
REM %DATE% depende del locale de Windows y es fragil bajo el Programador de
REM tareas; Get-Item .Length no. Fallo aqui nunca bloquea el pipeline (exit 0).
if "%~1"=="" exit /b 0
powershell -NoProfile -Command "$l='%~1'; if ((Test-Path $l) -and ((Get-Item $l).Length -gt 5MB)) { Move-Item -Force $l ($l+'.1') }" >nul 2>&1
exit /b 0
