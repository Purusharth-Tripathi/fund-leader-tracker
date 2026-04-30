@echo off
setlocal enabledelayedexpansion
REM Fund Leader Tracker - Daily Refresh Script
REM Runs the live holdings refresh workflow with automatic batch selection,
REM then logs the result and syncs updated artifacts if anything changed.

REM Set the working directory to the script's location
cd /d "%~dp0"

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Log file with timestamp
set LOGFILE=logs\scheduled_run_%date:~-4,4%%date:~-10,2%%date:~-7,2%.log

echo ================================================== >> %LOGFILE%
echo Fund Leader Tracker - Scheduled Refresh Run >> %LOGFILE%
echo Date/Time: %date% %time% >> %LOGFILE%
echo Working Directory: %CD% >> %LOGFILE%
echo ================================================== >> %LOGFILE%
echo. >> %LOGFILE%

REM Run the daily refresh workflow (main.py auto-selects batch_a/batch_b by date)
C:\Users\ptripathi22\AppData\Local\Microsoft\WindowsApps\python.exe main.py refresh >> %LOGFILE% 2>&1
set EXITCODE=%ERRORLEVEL%

echo. >> %LOGFILE%
echo Refresh exit code: %EXITCODE% >> %LOGFILE%

REM Sync only on successful refresh execution
if %EXITCODE% EQU 0 (
    echo. >> %LOGFILE%
    echo ================================================== >> %LOGFILE%
    echo Syncing refreshed artifacts to GitHub... >> %LOGFILE%
    echo ================================================== >> %LOGFILE%

    git config --global credential.helper store >> %LOGFILE% 2>&1
    git add data/fund_leaders.db data/cache output/leaders.csv output/leaders.json output/reports >> %LOGFILE% 2>&1
    git diff --cached --quiet
    if !ERRORLEVEL! EQU 0 (
        echo No changed artifacts to commit. >> %LOGFILE%
    ) else (
        git commit -m "Auto-refresh: %date% %time%" >> %LOGFILE% 2>&1
        git push origin main >> %LOGFILE% 2>&1
        if !ERRORLEVEL! EQU 0 (
            echo GitHub sync successful! >> %LOGFILE%
        ) else (
            echo WARNING: GitHub sync failed >> %LOGFILE%
        )
    )
) else (
    echo WARNING: Refresh failed; skipping GitHub sync. >> %LOGFILE%
)

echo. >> %LOGFILE%
echo ================================================== >> %LOGFILE%
echo Refresh completed at %time% >> %LOGFILE%
echo ================================================== >> %LOGFILE%
echo. >> %LOGFILE%

exit /b %EXITCODE%
