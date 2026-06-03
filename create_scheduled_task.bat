@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ========================================
echo   bili2doc Scheduled Task Creator
echo ========================================
echo.
echo This will create a Windows Scheduled Task
echo to run bili2doc automatically at night.
echo.

set /p START_TIME="Enter start time (HH:MM, e.g. 23:00): "

if "%START_TIME%"=="" (
    set START_TIME=23:00
)

echo.
echo Creating scheduled task...
echo Task Name: bili2doc_night_run
echo Start Time: %START_TIME%
echo Program: %~dp0night_run.bat
echo.

schtasks /create /tn "bili2doc_night_run" /tr "\"%~dp0night_run.bat\"" /sc daily /st %START_TIME% /ru "%USERNAME%" /f

if %errorlevel% equ 0 (
    echo.
    echo SUCCESS! Scheduled task created.
    echo Task will run daily at %START_TIME%
    echo.
    echo To view: schtasks /query /tn "bili2doc_night_run"
    echo To delete: schtasks /delete /tn "bili2doc_night_run" /f
) else (
    echo.
    echo FAILED! Please run as Administrator.
)

echo.
pause
