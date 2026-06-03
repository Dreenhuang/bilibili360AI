@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ========================================
echo   bili2doc - Bilibili Video to DOCX
echo   Version: v48 (Production)
echo   Date: 2026-06-03
echo ========================================
echo.

REM Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

echo [1/3] Checking dependencies...
pip show pyautogui >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing dependencies...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install dependencies.
        pause
        exit /b 1
    )
)
echo Dependencies OK.
echo.

echo [2/3] Checking browser...
if not exist "D:\360AI\360aibrowser\Application\360aibrowser.exe" (
    echo WARNING: 360AI Browser not found at default path.
    echo Please install 360AI Browser and update BROWSER_PATH in bili2doc.py
    echo.
)

echo [3/3] Starting bili2doc...
echo.

cd /d "%~dp0"
python bili2doc.py %*

echo.
echo ========================================
echo   Process completed.
echo   Press any key to exit...
echo ========================================
pause >nul