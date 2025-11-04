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

python main.py >> %LOGFILE% 2>&1

REM Log completion
echo. >> %LOGFILE%
echo ================================================== >> %LOGFILE%
echo Analysis completed at %time% >> %LOGFILE%
echo ================================================== >> %LOGFILE%
echo. >> %LOGFILE%

exit /b 0
