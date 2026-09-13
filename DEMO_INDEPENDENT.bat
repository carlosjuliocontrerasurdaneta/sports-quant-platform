@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run INSTALL_LOCAL.bat first.
  exit /b 1
)
".venv\Scripts\python.exe" scripts\price_independent.py --model examples\independent_model.json --quotes examples\independent_quotes.json --as-of 2026-09-10T12:00:00Z --max-quote-age-min 90
exit /b %errorlevel%
