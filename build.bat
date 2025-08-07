@echo off
echo ========================================
echo  Simple Build with UUID Fix
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

REM Clean previous builds
if exist "build" rmdir /s /q "build"
if exist "*.spec" del /q "*.spec"image.png

REM Get version
for /f "delims=" %%i in ('python -c "import sys; sys.path.insert(0, 'src'); from src import __version__; print(__version__)"') do set VERSION=%%i

REM Set output filename
set APP_NAME=SwitchboardMultiUserMonitor
set OS_NAME=Windows
set OUTPUT_NAME=%APP_NAME%-%VERSION%-%OS_NAME%.exe

echo Building: %OUTPUT_NAME%

REM Build with PyInstaller - Focus on UUID and core modules
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "temp_build" ^
    --add-data "src/ui/multiusersync/images;ui/multiusersync/images" ^
    --add-data "src/external/sync_sandbox.bat;external" ^
    --add-data "CHANGELOG.md;ui/changelog" ^
    --distpath "dist" ^
    --workpath "build" ^
    --clean ^
    --icon "src/ui/multiusersync/images/switchboard.ico" ^
    --hidden-import sqlite3 ^
    --hidden-import uuid ^
    --hidden-import shlex ^
    --hidden-import pythonosc ^
    --hidden-import pythonosc.dispatcher ^
    --hidden-import pythonosc.udp_client ^
    --hidden-import pythonosc.osc_server ^
    --hidden-import pythonosc.osc_message ^
    --hidden-import pythonosc.osc_bundle ^
    --hidden-import pythonosc.osc_types ^
    --hidden-import aioquic ^
    --hidden-import aioquic.asyncio ^
    --hidden-import aioquic.h3 ^
    --hidden-import aioquic.h3.connection ^
    --hidden-import aioquic.h3.events ^
    --hidden-import aioquic.quic ^
    --hidden-import aioquic.quic.connection ^
    --hidden-import aioquic.quic.events ^
    --hidden-import six ^
    --hidden-import ctypes ^
    --hidden-import ctypes.wintypes ^
    --hidden-import ctypes.util ^
    --hidden-import xml ^
    --hidden-import xml.etree ^
    --hidden-import xml.etree.ElementTree ^
    --hidden-import xml.etree.ElementPath ^
    --hidden-import dataclasses ^
    --hidden-import pathlib ^
    --hidden-import typing ^
    --hidden-import importlib ^
    --hidden-import importlib.util ^
    --hidden-import collections ^
    --hidden-import collections.abc ^
    --hidden-import enum ^
    --hidden-import functools ^
    --hidden-import itertools ^
    --hidden-import datetime ^
    --hidden-import json ^
    --hidden-import os ^
    --hidden-import sys ^
    --hidden-import threading ^
    --hidden-import logging ^
    --hidden-import subprocess ^
    --hidden-import shutil ^
    --hidden-import tempfile ^
    --hidden-import platform ^
    --hidden-import time ^
    --hidden-import re ^
    --hidden-import copy ^
    --hidden-import inspect ^
    --hidden-import ast ^
    --hidden-import traceback ^
    --hidden-import warnings ^
    --hidden-import glob ^
    --hidden-import stat ^
    --exclude-module tkinter ^
    --exclude-module matplotlib ^
    --exclude-module numpy ^
    --exclude-module scipy ^
    --exclude-module pandas ^
    --exclude-module IPython ^
    --exclude-module jupyter ^
    --paths src ^
    src/main.py

REM Rename output
if exist "dist\temp_build.exe" (
    move "dist\temp_build.exe" "dist\%OUTPUT_NAME%"
    echo.
    echo ========================================
    echo  BUILD SUCCESSFUL!
    echo ========================================
    echo Output: dist\%OUTPUT_NAME%
    
    REM Display file size
    for %%A in ("dist\%OUTPUT_NAME%") do (
        set /a "size_mb=%%~zA / 1024 / 1024"
        echo Size: %%~zA bytes ^(!size_mb! MB^)
    )
    echo.
    echo Focused build with UUID fix
    echo Direct entry: src/main.py
) else (
    echo ERROR: Build failed!
)

REM Clean up
if exist "temp_build.spec" del /q "temp_build.spec"

pause 