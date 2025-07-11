#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to validate sync script path detection
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

from ui.copy_dialog import CopyDialog
from PySide6.QtWidgets import QApplication

def test_sync_script_path():
    """Test sync script path detection"""
    app = QApplication(sys.argv)
    
    # Create a dummy copy dialog
    dialog = CopyDialog([], Path.cwd() / "Content")
    
    # Test script path detection
    script_path = dialog._get_sync_script_path()
    
    print(f"Detected script path: {script_path}")
    
    if script_path:
        print(f"Script exists: {script_path.exists()}")
        if script_path.exists():
            print(f"Script size: {script_path.stat().st_size} bytes")
    else:
        print("No script found")
    
    # Test PyInstaller detection
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        print("Running as PyInstaller bundle")
        print(f"Bundle directory: {sys._MEIPASS}")
    else:
        print("Running as Python script")
        print(f"Source directory: {Path(__file__).parent}")
    
    app.quit()

if __name__ == "__main__":
    test_sync_script_path() 