@echo off
setlocal EnableExtensions DisableDelayedExpansion
title JS

rem Run from the project folder even when launched by double-clicking.
pushd "%~dp0"
if errorlevel 1 goto location_error

set "UART_PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "%UART_PYTHON%" goto check_environment

echo Preparing the Python environment for JS...
rem Prefer the Windows Python launcher; fall back to Python on PATH.
py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>&1
if errorlevel 1 goto try_python
py -3 -m venv "%~dp0.venv"
if errorlevel 1 goto environment_error
goto check_environment

:try_python
python -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>&1
if errorlevel 1 goto python_missing
python -m venv "%~dp0.venv"
if errorlevel 1 goto environment_error

:check_environment
"%UART_PYTHON%" -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>&1
if errorlevel 1 goto environment_error

rem Install every project dependency, not just the first missing module.
"%UART_PYTHON%" -c "from PySide6 import QtCore, QtGui, QtWidgets; import pyqtgraph, serial, numpy, scipy" >nul 2>&1
if not errorlevel 1 goto launch

echo Installing required packages. The first run may take several minutes.
echo An Internet connection is needed for this step.
"%UART_PYTHON%" -m pip install --disable-pip-version-check -e .
if errorlevel 1 goto install_error

:launch
echo Starting JS...
rem Forward options, for example: run.bat --demo
"%UART_PYTHON%" "%~dp0main.py" %*
set "UART_EXIT_CODE=%ERRORLEVEL%"
if not "%UART_EXIT_CODE%"=="0" goto application_error
popd
exit /b 0

:python_missing
echo.
echo Python 3.10 or newer was not found.
echo Install Python from https://www.python.org/downloads/windows/
echo Enable the installer option to add Python to PATH, then run this file again.
set "UART_EXIT_CODE=1"
goto failure

:environment_error
echo.
echo The local Python environment could not be created or started.
echo Make sure Python 3.10 or newer is installed and this folder is writable.
echo If a .venv folder already exists, rename it and run this launcher again.
set "UART_EXIT_CODE=1"
goto failure

:install_error
echo.
echo Package installation failed. Review the error above.
echo Check your Internet connection and your access to Python package downloads.
set "UART_EXIT_CODE=1"
goto failure

:application_error
echo.
echo JS exited with code %UART_EXIT_CODE%. Review the error above.

:failure
echo.
echo Press any key to close this window.
pause >nul
popd
exit /b %UART_EXIT_CODE%

:location_error
echo Could not open the project folder. Extract the ZIP before running this file.
pause
exit /b 1
