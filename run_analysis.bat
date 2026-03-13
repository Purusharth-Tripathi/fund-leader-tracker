@echo off
REM Fund Leader Tracker - Daily Analysis Runner
REM This script runs the fund analysis and logs output

cd /d C:\Users\ptripathi22\Claude\fund-leader-tracker

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Set log file with timestamp
set LOGFILE=logs\analysis_%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%.log
set LOGFILE=%LOGFILE: =0%

echo ============================================= >> "%LOGFILE%" 2>&1
echo Fund Leader Tracker - Analysis Run >> "%LOGFILE%" 2>&1
echo Date: %date% %time% >> "%LOGFILE%" 2>&1
echo ============================================= >> "%LOGFILE%" 2>&1
echo. >> "%LOGFILE%" 2>&1

REM Run the Python script
python main.py >> "%LOGFILE%" 2>&1

REM Check exit code
if %ERRORLEVEL% EQU 0 (
    echo. >> "%LOGFILE%" 2>&1
    echo [SUCCESS] Analysis completed successfully >> "%LOGFILE%" 2>&1

    REM Auto-commit and push updated data to GitHub
    echo. >> "%LOGFILE%" 2>&1
    echo [GIT] Pushing updated data to GitHub... >> "%LOGFILE%" 2>&1
    git add data/fund_leaders.db output/leaders.csv output/leaders.json >> "%LOGFILE%" 2>&1
    git commit -m "Auto-update: Analysis run %date% %time:~0,5%" >> "%LOGFILE%" 2>&1
    git push origin main >> "%LOGFILE%" 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo [GIT] Push successful >> "%LOGFILE%" 2>&1
    ) else (
        echo [GIT] Push failed - data saved locally only >> "%LOGFILE%" 2>&1
    )
) else (
    echo. >> "%LOGFILE%" 2>&1
    echo [ERROR] Analysis failed with exit code: %ERRORLEVEL% >> "%LOGFILE%" 2>&1
)

echo ============================================= >> "%LOGFILE%" 2>&1
echo End Time: %date% %time% >> "%LOGFILE%" 2>&1
echo ============================================= >> "%LOGFILE%" 2>&1

exit /b %ERRORLEVEL%
