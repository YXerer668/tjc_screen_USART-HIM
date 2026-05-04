@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "PYTHONPATH=%SCRIPT_DIR%;%PYTHONPATH%"
python -m usarthmi %*
if errorlevel 9009 (
  echo Python was not found in PATH.
  exit /b 9009
)
exit /b %errorlevel%

