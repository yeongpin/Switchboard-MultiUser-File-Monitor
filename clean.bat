@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Switchboard MultiUser File Monitor Clean
echo ========================================

:: Check if virtual environment exists
if not exist "venv" (
    echo No virtual environment found to clean.
    pause
    exit /b 0
)

:: Confirm deletion
echo This will delete the virtual environment and all installed packages.
set /p confirm="Are you sure? (y/N): "

if /i "!confirm!" neq "y" (
    echo Cleanup cancelled.
    pause
    exit /b 0
)

:: Remove virtual environment
echo Removing virtual environment...
rmdir /s /q venv
if errorlevel 1 (
    echo Error: Failed to remove virtual environment
    echo You may need to close any programs using files in the venv directory
    pause
    exit /b 1
)

echo.
echo ========================================
echo Cleanup completed successfully!
echo ========================================
echo.
echo To recreate the environment, run:
echo   setup.bat
echo.
pause 