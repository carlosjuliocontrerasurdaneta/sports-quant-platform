@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% neq 0 goto :python
py -3 scripts\setup_local.py --verify
exit /b %errorlevel%
:python
python scripts\setup_local.py --verify
exit /b %errorlevel%
