@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ========================================
echo   bili2doc Night Run Launcher
echo   Version: v49 (Night Mode)
echo   Date: 2026-06-03
echo ========================================
echo.

cd /d "%~dp0"

echo [%time%] Starting bili2doc in night mode...
echo [%time%] Browser will auto minimize after each video
echo.

python bili2doc.py

echo.
echo [%time%] Process completed.
echo Check logs/ directory for details.
echo Check night_run_report.json for summary.
echo.
pause
