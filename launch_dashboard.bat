@echo off
REM Fund Leader Tracker - Dashboard Launcher
REM This script launches the interactive web dashboard

echo ====================================================
echo Fund Leader Tracker - Dashboard Launcher
echo ====================================================
echo.
echo Starting dashboard...
echo Dashboard will open in your default browser
echo.
echo Press Ctrl+C to stop the dashboard server
echo ====================================================
echo.

REM Set the working directory to the script's location
cd /d "%~dp0"

REM Launch Streamlit dashboard
python -m streamlit run dashboard.py

pause
