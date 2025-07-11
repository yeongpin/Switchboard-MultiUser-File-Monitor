@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Switchboard MultiUser File Monitor
echo ========================================

:: Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Error: Failed to create virtual environment
        echo Please make sure Python is installed and accessible
        pause
        exit /b 1
    )
    echo Virtual environment created successfully
) else (
    echo Virtual environment already exists
)

:: Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo Error: Failed to activate virtual environment
    pause
    exit /b 1
)

:: Install/update dependencies
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo Warning: Some dependencies may not have been installed correctly
)

:: Run the application
echo.
echo Starting Switchboard MultiUser File Monitor...
echo.
python src/main.py

:: Deactivate virtual environment
deactivate

echo.
echo Application finished.
pause 