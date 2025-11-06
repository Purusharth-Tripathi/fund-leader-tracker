@echo off
REM Fund Leader Tracker - Daily Analysis Script
REM This script runs the fund analysis and logs the output

REM Set the working directory to the script's location
cd /d "%~dp0"

REM Log file with timestamp
set LOGFILE=logs\scheduled_run_%date:~-4,4%%date:~-10,2%%date:~-7,2%.log

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Run the analysis and append output to log file
echo ================================================== >> %LOGFILE%
echo Fund Leader Tracker - Scheduled Run >> %LOGFILE%
echo Date/Time: %date% %time% >> %LOGFILE%
echo ================================================== >> %LOGFILE%
echo. >> %LOGFILE%

C:\Users\ptripathi22\AppData\Local\Microsoft\WindowsApps\python.exe main.py >> %LOGFILE% 2>&1

REM Check if analysis was successful
if %ERRORLEVEL% EQU 0 (
    echo. >> %LOGFILE%
    echo ================================================== >> %LOGFILE%
    echo Syncing results to GitHub... >> %LOGFILE%
    echo ================================================== >> %LOGFILE%

    REM Configure git to use stored credentials
    git config --global credential.helper store

    REM Add updated files
    git add data/fund_leaders.db output/leaders.csv output/leaders.json >> %LOGFILE% 2>&1

    REM Commit with timestamp
    git commit -m "Auto-update: Analysis run %date% %time%" >> %LOGFILE% 2>&1

    REM Push to GitHub
    git push origin main >> %LOGFILE% 2>&1

    if %ERRORLEVEL% EQU 0 (
        echo GitHub sync successful! >> %LOGFILE%
    ) else (
        echo WARNING: GitHub sync failed >> %LOGFILE%
    )
)

REM Log completion
echo. >> %LOGFILE%
echo ================================================== >> %LOGFILE%
echo Analysis completed at %time% >> %LOGFILE%
echo ================================================== >> %LOGFILE%
echo. >> %LOGFILE%

exit /b 0
