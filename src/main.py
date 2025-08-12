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
from PySide6.QtGui import QIcon, QGuiApplication

from ui.multiusersync.main_window import MainWindow
from ui.switchboard import SwitchboardWidget
from ui.ndisplaymonitor import NDisplayMonitorTab
from ui.switchboard_new import SwitchboardNewTab
from ui.changelog import ChangelogWidget
from ui.svn import SVNWidget
from ui.settings import SettingsTab
from ui.switchboard_listener import SwitchboardListenerTab
from utils.logger import setup_logger

# Get version - handle both direct run and packaged scenarios
try:
    from src import __version__
except ImportError:
    try:
        # When running from src directory
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from __init__ import __version__
    except ImportError:
        # Fallback version
        __version__ = "1.0.0"


class IntegratedMainWindow(QMainWindow):
    """Main window that integrates both Switchboard and MultiUser File Monitor"""
    
    def __init__(self):
        super().__init__()
        self.logger = setup_logger()
        self.logger.info("Starting Integrated Switchboard Application")
        
        # Initialize components
        self.switchboard_dialog = None
        self.multiuser_widget = None
        self.changelog_widget = None
        self.svn_widget = None
        self.ndisplay_widget = None

        # Initialize index for tab ordering
        self.index = type('Index', (), {})()
        self.index.switchboard_new = 0
        self.index.listener_widget = 1
        self.index.switchboard_dialog = -2
        self.index.ndisplay_monitor = 3
        self.index.multiuser_widget = 4
        self.index.svn_widget = 5
        self.index.changelog_widget = 6
        self.index.settings_widget = 7


        self.active_tab = 0
        

        self.setup_ui()
        self.initialize_tabs()
        
    def setup_ui(self):
        """Setup the main window UI"""
        self.setWindowTitle("Switchboard MultiUser File Monitor" + " " + __version__)
        # Default size then center on screen
        self.resize(1350, 800)
        self.center_on_screen()
        
        # Create central widget with tab layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

    def center_on_screen(self):
        """Center the main window on the current screen."""
        try:
            screen = self.screen() or QGuiApplication.primaryScreen()
            if screen is None:
                return
            rect = screen.availableGeometry()
            x = int(rect.center().x() - self.width() / 2)
            y = int(rect.center().y() - self.height() / 2)
            self.move(x, y)
        except Exception:
            pass
        
    def initialize_tabs(self):
        """Initialize the tab widgets"""
        # Create a list to store tabs in order
        tabs_to_add = []
        
        # Initialize Switchboard (Tab 0)
        try:
            self.logger.info("Initializing Switchboard...")
            self.switchboard_widget = SwitchboardWidget()
            self.logger.info("Using embedded Switchboard (full interface)")
            tabs_to_add.append((self.index.switchboard_dialog, self.switchboard_widget, "Switchboard Old"))
            self.logger.info("Switchboard tab added successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Switchboard: {e}")
            placeholder = QWidget()
            placeholder.setLayout(QVBoxLayout())
            from PySide6.QtWidgets import QLabel
            label = QLabel("Switchboard initialization failed")
            label.setAlignment(Qt.AlignCenter)
            placeholder.layout().addWidget(label)
            tabs_to_add.append((self.index.switchboard_dialog, placeholder, "Switchboard Old"))
        
        # Initialize MultiUser File Monitor (Tab 1)
        try:
            self.logger.info("Initializing MultiUser File Monitor...")
            self.multiuser_widget = MainWindow()
            tabs_to_add.append((self.index.multiuser_widget, self.multiuser_widget, "MultiUser File Monitor"))
            self.logger.info("MultiUser File Monitor tab added successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize MultiUser File Monitor: {e}")
            placeholder = QWidget()
            placeholder.setLayout(QVBoxLayout())
            from PySide6.QtWidgets import QLabel
            label = QLabel("MultiUser File Monitor not available")
            label.setAlignment(Qt.AlignCenter)
            placeholder.layout().addWidget(label)
            tabs_to_add.append((self.index.multiuser_widget, placeholder, "MultiUser File Monitor"))
        
        # Initialize nDisplay Monitor (Tab 2)
        try:
            self.logger.info("Initializing nDisplay Monitor...")
            self.ndisplay_widget = NDisplayMonitorTab()
            tabs_to_add.append((self.index.ndisplay_monitor, self.ndisplay_widget, "nDisplay Monitor"))
            self.logger.info("nDisplay Monitor tab added successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize nDisplay Monitor: {e}")
            placeholder = QWidget()
            placeholder.setLayout(QVBoxLayout())
            from PySide6.QtWidgets import QLabel
            label = QLabel("nDisplay Monitor not available")
            label.setAlignment(Qt.AlignCenter)
            placeholder.layout().addWidget(label)
            tabs_to_add.append((self.index.ndisplay_monitor, placeholder, "nDisplay Monitor"))

        # Initialize Switchboard New (Tab 5)
        try:
            self.logger.info("Initializing Switchboard New...")
            self.switchboard_new_widget = SwitchboardNewTab()
            tabs_to_add.append((self.index.switchboard_new, self.switchboard_new_widget, "Switchboard New"))
            self.logger.info("Switchboard New tab added successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Switchboard New: {e}")
            placeholder = QWidget()
            placeholder.setLayout(QVBoxLayout())
            from PySide6.QtWidgets import QLabel
            label = QLabel("Switchboard New not available")
            label.setAlignment(Qt.AlignCenter)
            placeholder.layout().addWidget(label)
            tabs_to_add.append((self.index.switchboard_new, placeholder, "Switchboard New"))

        # Initialize SVN Version Control (Tab 3)
        try:
            self.logger.info("Initializing SVN Version Control...")
            self.svn_widget = SVNWidget()
            tabs_to_add.append((self.index.svn_widget, self.svn_widget, "SVN Version Control"))
            self.logger.info("SVN Version Control tab added successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize SVN Version Control: {e}")
            placeholder = QWidget()
            placeholder.setLayout(QVBoxLayout())
            from PySide6.QtWidgets import QLabel
            label = QLabel("SVN Version Control not available")
            label.setAlignment(Qt.AlignCenter)
            placeholder.layout().addWidget(label)
            tabs_to_add.append((self.index.svn_widget, placeholder, "SVN Version Control"))
        
        # Initialize Changelog (Tab 4)
        try:
            self.logger.info("Initializing Changelog...")
            self.changelog_widget = ChangelogWidget()
            tabs_to_add.append((self.index.changelog_widget, self.changelog_widget, "Changelog"))
            self.logger.info("Changelog tab added successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Changelog: {e}")
            placeholder = QWidget()
            placeholder.setLayout(QVBoxLayout())
            from PySide6.QtWidgets import QLabel
            label = QLabel("Changelog not available")
            label.setAlignment(Qt.AlignCenter)
            placeholder.layout().addWidget(label)
            tabs_to_add.append((self.index.changelog_widget, placeholder, "Changelog"))

        # Initialize Settings (Tab 6)
        try:
            self.logger.info("Initializing Settings tab...")
            self.settings_widget = SettingsTab()
            tabs_to_add.append((self.index.settings_widget, self.settings_widget, "Settings"))
            self.logger.info("Settings tab added successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Settings tab: {e}")
            placeholder = QWidget()
            placeholder.setLayout(QVBoxLayout())
            from PySide6.QtWidgets import QLabel
            label = QLabel("Settings not available")
            label.setAlignment(Qt.AlignCenter)
            placeholder.layout().addWidget(label)
            tabs_to_add.append((self.index.settings_widget, placeholder, "Settings"))

        # Initialize Switchboard Listener (Tab 7)
        try:
            self.logger.info("Initializing Switchboard Listener tab...")
            self.listener_widget = SwitchboardListenerTab()
            tabs_to_add.append((self.index.listener_widget, self.listener_widget, "Switchboard Listener"))
            self.logger.info("Switchboard Listener tab added successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Switchboard Listener tab: {e}")
            placeholder = QWidget()
            placeholder.setLayout(QVBoxLayout())
            from PySide6.QtWidgets import QLabel
            label = QLabel("Switchboard Listener not available")
            label.setAlignment(Qt.AlignCenter)
            placeholder.layout().addWidget(label)
            tabs_to_add.append((self.index.listener_widget, placeholder, "Switchboard Listener"))
        
        # Add tabs in the correct order based on index
        tabs_to_add.sort(key=lambda x: x[0])  # Sort by index
        for index, widget, title in tabs_to_add:
            # If index is negative, do not display this tab (hidden)
            if index is None or index < 0:
                continue
            self.tab_widget.addTab(widget, title)
        # Set active tab on startup
        try:
            total_tabs = self.tab_widget.count()
            target = int(self.active_tab)
            if target < 0:
                target = 0
            if target >= total_tabs:
                target = total_tabs - 1 if total_tabs > 0 else 0
            self.tab_widget.setCurrentIndex(target)
        except Exception:
            pass
    
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
            
            # Additional cleanup: kill Switchboard-related Python processes and device listeners
            try:
                # Get current process ID to avoid killing ourselves
                current_pid = os.getpid()
                
                # First, try to disconnect all devices gracefully
                try:
                    if hasattr(self, 'switchboard_widget') and self.switchboard_widget:
                        # Try to access device manager through switchboard widget
                        from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
                        dialog = get_current_switchboard_dialog()
                        if dialog and hasattr(dialog, 'device_manager'):
                            self.logger.info("Disconnecting all devices...")
                            devices = dialog.device_manager.devices()
                            for device in devices:
                                try:
                                    if hasattr(device, 'disconnect_listener'):
                                        device.disconnect_listener()
                                except Exception:
                                    pass
                except Exception as e:
                    self.logger.warning(f"Could not gracefully disconnect devices: {e}")
                
                # Kill Python processes that are Switchboard-related
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
                                         'listener' in commandline or
                                         'unreal' in commandline)):
                                        
                                        subprocess.run(['taskkill', '/F', '/PID', str(pid)], 
                                                     capture_output=True, check=False,
                                                     startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW)
                                        self.logger.info(f"Killed Switchboard-related Python process {pid}")
                                except (ValueError, IndexError):
                                    continue
                                    
                # Also kill any listener.exe processes
                subprocess.run(['taskkill', '/F', '/IM', 'listener.exe'], 
                             capture_output=True, check=False, 
                             startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW)
                             
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
        
        # Hide window immediately for better user experience
        self.hide()
        event.accept()  # Accept the event first
        
        # Close UI widgets on the main thread to avoid timer warnings
        self.close_ui_widgets_on_main_thread()
        
        # Run process cleanup in background
        self.run_cleanup_in_background()

    def close_ui_widgets_on_main_thread(self):
        """Close child widgets safely on the GUI thread."""
        try:
            if self.multiuser_widget:
                try:
                    self.multiuser_widget.close()
                except Exception as e:
                    self.logger.error(f"Error closing MultiUser widget: {e}")
            if self.switchboard_widget:
                try:
                    self.switchboard_widget.close()
                except Exception as e:
                    self.logger.error(f"Error closing Switchboard widget: {e}")
            if self.changelog_widget and hasattr(self.changelog_widget, 'close'):
                try:
                    self.changelog_widget.close()
                except Exception as e:
                    self.logger.error(f"Error closing Changelog widget: {e}")
            if self.svn_widget and hasattr(self.svn_widget, 'close'):
                try:
                    self.svn_widget.close()
                except Exception as e:
                    self.logger.error(f"Error closing SVN widget: {e}")
            if self.ndisplay_widget and hasattr(self.ndisplay_widget, 'close'):
                try:
                    self.ndisplay_widget.close()
                except Exception as e:
                    self.logger.error(f"Error closing nDisplay widget: {e}")
            if hasattr(self, 'listener_widget') and self.listener_widget:
                try:
                    self.listener_widget.close()
                except Exception as e:
                    self.logger.error(f"Error closing Listener widget: {e}")
        except Exception as e:
            self.logger.error(f"Error closing widgets: {e}")
    
    def run_cleanup_in_background(self):
        """Run cleanup operations in background thread"""
        from PySide6.QtCore import QThread, QTimer
        
        def cleanup_thread():
            """Background cleanup function"""
            try:
                # Clean up all processes only (no UI ops in background thread)
                self.cleanup_all_processes()
                
                self.logger.info("Background cleanup completed")
                
            except Exception as e:
                self.logger.error(f"Error in background cleanup: {e}")
            finally:
                # Schedule application quit on main thread
                QTimer.singleShot(0, self.quit_application)
        
        # Start cleanup in a separate thread
        import threading
        cleanup_thread_obj = threading.Thread(target=cleanup_thread, daemon=True)
        cleanup_thread_obj.start()
    
    def quit_application(self):
        """Quit the application from main thread"""
        from PySide6.QtWidgets import QApplication
        QApplication.quit()


def main():
    """Application entry point"""
    # Setup logging
    logger = setup_logger()
    logger.info("Starting Switchboard MultiUser File Monitor")
    
    # Create QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("Switchboard MultiUser File Monitor")
    app.setApplicationVersion("1.2.1")
    
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