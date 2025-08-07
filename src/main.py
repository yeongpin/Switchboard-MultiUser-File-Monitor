#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Switchboard MultiUser File Monitor
Main entry point for the application with integrated Switchboard
"""

import sys
import os
import subprocess
from pathlib import Path

# Add the src directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from ui.multiusersync.main_window import MainWindow
from ui.switchboard import SwitchboardWidget
from utils.logger import setup_logger


class IntegratedMainWindow(QMainWindow):
    """Main window that integrates both Switchboard and MultiUser File Monitor"""
    
    def __init__(self):
        super().__init__()
        self.logger = setup_logger()
        self.logger.info("Starting Integrated Switchboard Application")
        
        # Initialize components
        self.switchboard_dialog = None
        self.multiuser_widget = None
        
        self.setup_ui()
        self.initialize_tabs()
        
    def setup_ui(self):
        """Setup the main window UI"""
        self.setWindowTitle("Switchboard MultiUser File Monitor")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget with tab layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
    def initialize_tabs(self):
        """Initialize the tab widgets"""
        # Initialize Switchboard (Tab 1) - Choose between embedded and simple versions
        try:
            self.logger.info("Initializing Switchboard...")
            
            self.switchboard_widget = SwitchboardWidget()
            self.logger.info("Using embedded Switchboard (full interface)")
            
            # Add Switchboard as first tab
            self.tab_widget.addTab(
                self.switchboard_widget, 
                "Switchboard"
            )
            self.logger.info("Switchboard tab added successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Switchboard: {e}")
            # Create a placeholder widget for Switchboard tab
            placeholder = QWidget()
            placeholder.setLayout(QVBoxLayout())
            from PySide6.QtWidgets import QLabel
            label = QLabel("Switchboard initialization failed")
            label.setAlignment(Qt.AlignCenter)
            placeholder.layout().addWidget(label)
            
            self.tab_widget.addTab(placeholder, "Switchboard")
        
        # Initialize MultiUser File Monitor (Tab 2)
        try:
            self.logger.info("Initializing MultiUser File Monitor...")
            self.multiuser_widget = MainWindow()
            
            # Add MultiUser as second tab
            self.tab_widget.addTab(
                self.multiuser_widget, 
                "MultiUser File Monitor"
            )
            self.logger.info("MultiUser File Monitor tab added successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize MultiUser File Monitor: {e}")
            # Create a placeholder widget for MultiUser tab
            placeholder = QWidget()
            placeholder.setLayout(QVBoxLayout())
            from PySide6.QtWidgets import QLabel
            label = QLabel("MultiUser File Monitor not available")
            label.setAlignment(Qt.AlignCenter)
            placeholder.layout().addWidget(label)
            
            self.tab_widget.addTab(placeholder, "MultiUser File Monitor")
    
    def cleanup_all_processes(self):
        """Clean up all related processes"""
        self.logger.info("Cleaning up all processes...")
        
        try:
            # Kill rsync processes - use subprocess.CREATE_NO_WINDOW to hide CMD windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            # Kill rsync processes
            subprocess.run(['taskkill', '/F', '/IM', 'rsync.exe'], 
                         capture_output=True, check=False, 
                         startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW)
            
            # Kill processes using port 8730 (Switchboard rsync port)
            result = subprocess.run(['netstat', '-ano'], 
                                  capture_output=True, text=True, check=False,
                                  startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if '8730' in line and 'LISTENING' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            pid = parts[-1]
                            try:
                                subprocess.run(['taskkill', '/F', '/PID', pid], 
                                             capture_output=True, check=False,
                                             startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW)
                                self.logger.info(f"Killed process {pid} using port 8730")
                            except Exception as e:
                                self.logger.error(f"Failed to kill process {pid}: {e}")
            
            # Additional cleanup: kill only Switchboard-related Python processes
            try:
                # Get current process ID to avoid killing ourselves
                current_pid = os.getpid()
                
                # Only kill Python processes that are actually using Switchboard ports or have Switchboard in their command line
                result = subprocess.run(['wmic', 'process', 'where', 'name="python.exe"', 'get', 'processid,commandline', '/format:csv'], 
                                      capture_output=True, text=True, check=False,
                                      startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')[1:]  # Skip header
                    for line in lines:
                        if line.strip() and ',' in line:
                            parts = line.split(',')
                            if len(parts) >= 3:
                                try:
                                    pid = int(parts[1].strip('"'))
                                    commandline = parts[2].strip('"').lower()
                                    
                                    # Only kill if it's not our process AND it's actually Switchboard-related
                                    if (pid != current_pid and 
                                        ('switchboard' in commandline or 
                                         'sbl_helper' in commandline or
                                         'listener' in commandline)):
                                        
                                        subprocess.run(['taskkill', '/F', '/PID', str(pid)], 
                                                     capture_output=True, check=False,
                                                     startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW)
                                        self.logger.info(f"Killed Switchboard-related Python process {pid}")
                                except (ValueError, IndexError):
                                    continue
            except Exception as e:
                self.logger.error(f"Error in additional cleanup: {e}")
                                
        except Exception as e:
            self.logger.error(f"Error cleaning up processes: {e}")
        
        # Final check - wait a moment and verify cleanup
        import time
        time.sleep(1)
        
        # Check if port 8730 is still in use
        final_check = subprocess.run(['netstat', '-ano'], 
                                    capture_output=True, text=True, check=False,
                                    startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW)
        if final_check.returncode == 0 and '8730' in final_check.stdout:
            self.logger.warning("Port 8730 is still in use after cleanup")
        else:
            self.logger.info("All process cleanup completed successfully")
    
    def closeEvent(self, event):
        """Handle application close event"""
        self.logger.info("Application closing...")
        
        # Clean up MultiUser widget
        if self.multiuser_widget:
            try:
                self.multiuser_widget.closeEvent(event)
            except Exception as e:
                self.logger.error(f"Error closing MultiUser widget: {e}")
        
        # Clean up Switchboard widget
        if self.switchboard_widget:
            try:
                self.switchboard_widget.closeEvent(event)
            except Exception as e:
                self.logger.error(f"Error closing Switchboard widget: {e}")
        
        # Clean up all processes
        self.cleanup_all_processes()
        
        event.accept()


def main():
    """Application entry point"""
    # Setup logging
    logger = setup_logger()
    logger.info("Starting Switchboard MultiUser File Monitor")
    
    # Create QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("Switchboard MultiUser File Monitor")
    app.setApplicationVersion("1.2.0")
    
    # Set application icon
    icon_path = Path(__file__).parent / "ui" / "multiusersync" / "images" / "switchboard.ico"
    if not icon_path.exists():
        # Try alternative paths for packaged environment
        if getattr(sys, 'frozen', False):
            # Running in a bundle (PyInstaller)
            base_path = Path(sys._MEIPASS)
            icon_path = base_path / "ui" / "multiusersync" / "images" / "switchboard.ico"
        else:
            # Running in normal Python environment
            icon_path = Path(__file__).parent / "ui" / "multiusersync" / "images" / "switchboard.ico"
    
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    
    # Create and show main window
    window = IntegratedMainWindow()
    window.show()
    
    # Execute the application
    try:
        result = app.exec()
        logger.info("Application closing...")
        return result
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Application error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 