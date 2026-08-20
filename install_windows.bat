@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (echo Python launcher ^(py^) not found. Install Python 3.11+ and try again.&pause&exit /b 1)
if not exist .venv py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (echo Failed to install dependencies.&pause&exit /b 1)
echo.
echo Installation complete.
echo Run start_windows.bat to start Mzizibet.
pause
