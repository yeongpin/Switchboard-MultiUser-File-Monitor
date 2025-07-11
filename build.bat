@echo off
echo ========================================
echo  Simple Build with UUID Fix
echo ========================================

REM Clean previous builds
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del /q "*.spec"

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
    --add-data "src/ui/images;ui/images" ^
    --distpath "dist" ^
    --workpath "build" ^
    --clean ^
    --icon "src/ui/images/switchboard.ico" ^
    --hidden-import sqlite3 ^
    --hidden-import uuid ^
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