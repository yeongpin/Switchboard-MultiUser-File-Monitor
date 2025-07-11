#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Switchboard MultiUser File Monitor
Main entry point for the application
"""

import sys
import os
from pathlib import Path

# Add the src directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from ui.main_window import MainWindow
from utils.logger import setup_logger
from PySide6.QtWidgets import QApplication


def main():
    """Application entry point"""
    # Setup logging
    logger = setup_logger()
    logger.info("Starting Switchboard MultiUser File Monitor")
    
    # Create QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("Switchboard MultiUser File Monitor")
    app.setApplicationVersion("1.0.0")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main() 