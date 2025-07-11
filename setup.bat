@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Switchboard MultiUser File Monitor Setup
echo ========================================

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ and add it to your PATH
    pause
    exit /b 1
)

echo Python found:
python --version

:: Remove existing virtual environment if it exists
if exist "venv" (
    echo Removing existing virtual environment...
    rmdir /s /q venv
)

:: Create new virtual environment
echo Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo Error: Failed to create virtual environment
    pause
    exit /b 1
)

:: Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo Error: Failed to activate virtual environment
    pause
    exit /b 1
)

:: Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

:: Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

:: Deactivate virtual environment
deactivate

echo.
echo ========================================
echo Setup completed successfully!
echo ========================================
echo.
echo You can now run the application using:
echo   run.bat
echo.
echo Or manually activate the environment:
echo   venv\Scripts\activate.bat
echo   python run.py
echo.
pause 