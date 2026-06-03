@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ========================================
echo   bili2doc Global Installer
echo   Version: v48 (Production)
echo   Date: 2026-06-03
echo ========================================
echo.
echo This installer will:
echo   1. Check system requirements
echo   2. Install Python dependencies
echo   3. Register bili2doc as a global command
echo   4. Create desktop shortcut
echo.
echo Press any key to continue...
pause >nul

echo.
echo [1/5] Checking Python installation...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.8+ from https://www.python.org/
    echo.
    echo After installation, restart your computer and run this installer again.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo Found: %PYVER%
echo.

echo [2/5] Installing dependencies...
cd /d "%~dp0"
pip install pyautogui pywin32 pillow
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)
echo Dependencies installed successfully.
echo.

echo [3/5] Registering global command...
set INSTALL_DIR=%LOCALAPPDATA%\bili2doc
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
)

copy /y "%~dp0bili2doc.py" "%INSTALL_DIR%\" >nul
copy /y "%~dp0requirements.txt" "%INSTALL_DIR%\" >nul
xcopy /s /e /y "%~dp0scripts\" "%INSTALL_DIR%\scripts\" >nul

REM Add to PATH
for /f "2 skip tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USERPATH=%%B"
echo %USERPATH% | findstr /i "bili2doc" >nul
if %errorlevel% neq 0 (
    reg add "HKCU\Environment" /v PATH /t REG_EXPAND_SZ /d "%USERPATH%;%INSTALL_DIR%" /f >nul
    echo Added to user PATH: %INSTALL_DIR%
) else (
    echo Already in PATH.
)

REM Create batch wrapper in install dir
echo @echo off > "%INSTALL_DIR%\bili2doc.cmd"
echo chcp 65001 ^>nul 2^>^&1 >> "%INSTALL_DIR%\bili2doc.cmd"
echo cd /d "%%~dp0" >> "%INSTALL_DIR%\bili2doc.cmd"
echo python bili2doc.py %%* >> "%INSTALL_DIR%\bili2doc.cmd"

echo Global command registered: bili2doc
echo.

echo [4/5] Creating desktop shortcut...
set DESKTOP=%USERPROFILE%\Desktop

REM Create shortcut using PowerShell
powershell -Command ^
"$WshShell = New-Object -comObject WScript.Shell; ^
$Shortcut = $WshShell.CreateShortcut('%DESKTOP%\bili2doc.lnk'); ^
$Shortcut.TargetPath = '%INSTALL_DIR%\bili2doc.cmd'; ^
$Shortcut.WorkingDirectory = '%INSTALL_DIR%'; ^
$Shortcut.Description = 'Bilibili Video to DOCX Tool'; ^
$Shortcut.Save()"

echo Desktop shortcut created: %DESKTOP%\bili2doc.lnk
echo.

echo [5/5] Verifying installation...
echo.
echo Installation directory: %INSTALL_DIR%
echo Files installed:
dir /b "%INSTALL_DIR%" 2>nul
echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo Usage:
echo   1. Double-click the desktop shortcut: bili2doc
echo   2. Or run from command line: bili2doc
echo   3. Or use the launcher: 启动bili2doc.bat
echo.
echo Press any key to exit...
pause >nul