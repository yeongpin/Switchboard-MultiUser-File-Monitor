# -*- coding: utf-8 -*-
"""
Switchboard Widget
Embedded full Switchboard interface for tabbed environment
"""

import sys
import os
import subprocess
import threading
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

print("=== SwitchboardWidget Debug ===")

# Add Switchboard to Python path - try multiple possible locations
current_dir = Path(__file__).parent.parent.parent
possible_switchboard_paths = [
    current_dir.parent / "Switchboard",  # ../Switchboard
    Path("D:/UE_5.6/Engine/Plugins/VirtualProduction/Switchboard/Source/Switchboard"),  # UE5.6 path
    Path("C:/Program Files/Epic Games/UE_5.6/Engine/Plugins/VirtualProduction/Switchboard/Source/Switchboard"),  # Program Files path
]

switchboard_found = False
for switchboard_path in possible_switchboard_paths:
    if switchboard_path.exists():
        sys.path.insert(0, str(switchboard_path))
        switchboard_found = True
        print(f"Found Switchboard at: {switchboard_path}")
        break

if not switchboard_found:
    print("Warning: Switchboard directory not found in any of the expected locations")

from utils.logger import get_logger

print("SwitchboardWidget module loaded successfully")


class SwitchboardWidget(QWidget):
    """Embedded Switchboard widget with full functionality"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self.switchboard_dialog = None
        self.script_manager = None
        
        print("SwitchboardWidget.__init__ called")
        self.setup_ui()
        
        # Use a timer to delay initialization
        QTimer.singleShot(500, self.initialize_switchboard)
        
    def setup_ui(self):
        """Setup the widget UI"""
        print("SwitchboardWidget.setup_ui called")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Main Switchboard area
        self.switchboard_container = QWidget()
        self.switchboard_layout = QVBoxLayout(self.switchboard_container)
        self.switchboard_layout.setContentsMargins(0, 0, 0, 0)
        
        # Loading indicator
        self.loading_label = QLabel("正在初始化 Switchboard...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setFont(QFont("Segoe UI", 12))
        self.loading_label.setStyleSheet("""
            QLabel {
                color: #7f8c8d;
                padding: 40px;
                background-color: #222222;
            }
        """)
        self.switchboard_layout.addWidget(self.loading_label)
        
        layout.addWidget(self.switchboard_container)
        
    def initialize_switchboard(self):
        """Initialize Switchboard in main thread"""
        try:
            self.logger.info("Starting Switchboard initialization...")
            
            # Import Switchboard components
            from switchboard import switchboard_scripting
            from switchboard.switchboard_dialog import SwitchboardDialog
            from switchboard.config import SETTINGS, CONFIG
            
            # Fix QToolTip issue before creating SwitchboardDialog
            self.fix_qtooltip_issue()
            
            # Initialize SETTINGS and CONFIG like in main Switchboard application
            self.logger.info("Initializing Switchboard settings and config...")
            SETTINGS.init()
            
            # Try to find a default config or create one
            config_path = self.find_or_create_default_config()
            if config_path:
                CONFIG.init(config_path)
                self.logger.info(f"Initialized CONFIG with: {config_path}")
            else:
                # Initialize with None to create a default config
                CONFIG.init(None)
                self.logger.info("Initialized CONFIG with default settings")
            
            # Initialize script manager
            self.script_manager = switchboard_scripting.ScriptManager()
            
            # Create Switchboard dialog (UI is already initialized in constructor)
            self.logger.info("Creating SwitchboardDialog...")
            self.switchboard_dialog = SwitchboardDialog(self.script_manager)
            self.logger.info("SwitchboardDialog created successfully")
            
            # Remove loading indicator
            self.loading_label.deleteLater()
            
            # Add Switchboard UI to container
            if hasattr(self.switchboard_dialog, 'window'):
                # Get the main widget from Switchboard
                main_widget = self.switchboard_dialog.window
                if main_widget:
                    # Reparent the widget to our container
                    main_widget.setParent(self.switchboard_container)
                    self.switchboard_layout.addWidget(main_widget)
                    
                    # Update window title and status
                    self.logger.info("Switchboard embedded successfully")
                    
                else:
                    self.logger.error("Could not find Switchboard main widget")
                    self.show_error("无法找到 Switchboard 主界面")
            else:
                self.logger.error("Switchboard dialog has no window attribute")
                self.show_error("Switchboard 界面不可用")
                
        except Exception as e:
            self.logger.error(f"Error initializing Switchboard: {e}")
            self.show_error(f"初始化 Switchboard 失败: {e}")
    
    def fix_qtooltip_issue(self):
        """Fix QToolTip instantiation issue by patching the problematic code"""
        try:
            from PySide6.QtWidgets import QToolTip
            from PySide6.QtCore import QPoint
            from PySide6.QtGui import QValidator
            import switchboard.switchboard_widgets as sb_widgets
            from pathlib import Path
            
            # Create a safe QToolTip class that doesn't fail on instantiation
            class SafeQToolTip:
                def __init__(self):
                    pass
                
                def showText(self, pos, text):
                    # Use the static method instead
                    QToolTip.showText(pos, text)
            
            # Replace QToolTip with our safe version
            import PySide6.QtWidgets
            PySide6.QtWidgets.QToolTip = SafeQToolTip
            
            self.logger.info("QToolTip class replaced with safe version")
            
        except Exception as e:
            self.logger.warning(f"Could not patch QToolTip issue: {e}")
            # Continue anyway, the error might not occur
    
    def find_or_create_default_config(self):
        """Find an existing config or return None to show create dialog"""
        try:
            # Use the same logic as config_detector.py to find configs
            from core.config_detector import ConfigDetector
            
            config_detector = ConfigDetector()
            available_configs = config_detector.get_available_configs()
            
            if available_configs:
                # Use the first available config
                config_path = str(available_configs[0])
                self.logger.info(f"Found config file: {config_path}")
                return config_path
            
            # If no config found, return None to show create dialog
            self.logger.info("No valid config files found, will show create dialog")
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding config: {e}")
            return None
    
    def create_default_config(self):
        """Create a default Switchboard configuration for packaged environment"""
        try:
            # Create a default config that works in packaged environment
            import tempfile
            import json
            
            # Create a temporary config file
            config_data = {
                "project_name": "DefaultProject",
                "uproject_path": "",
                "engine_dir": "",
                "multiuser_server_name": "Default",
                "multiuser_server_port": 8888,
                "listener_port": 2980,
                "osc_server_port": 6000,
                "rsync_port": 8730,
                "p4_enabled": False,
                "source_control_workspace": "",
                "project_workspace": "",
                "p4_sync_path": "",
                "p4_engine_path": "",
                "auto_join": True,
                "auto_build": False,
                "auto_deploy": False,
                "auto_launch": False,
                "auto_join_delay": 5.0,
                "auto_build_delay": 10.0,
                "auto_deploy_delay": 5.0,
                "auto_launch_delay": 5.0,
                "devices": [],
                "settings": {
                    "osc_server_port": 6000,
                    "rsync_port": 8730,
                    "listener_port": 2980,
                    "multiuser_server_port": 8888
                }
            }
            
            # Create config in user's documents folder
            import os
            from pathlib import Path
            
            # Create Switchboard configs directory in user's documents
            user_docs = Path.home() / "Documents" / "Switchboard" / "configs"
            user_docs.mkdir(parents=True, exist_ok=True)
            
            config_file = user_docs / "default_config.json"
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            
            self.logger.info(f"Created default config: {config_file}")
            return str(config_file)
            
        except Exception as e:
            self.logger.error(f"Error creating default config: {e}")
            return None
    
    def show_error(self, message):
        """Show error message"""
        self.loading_label.setText(f"错误: {message}")
        self.loading_label.setStyleSheet("""
            QLabel {
                color: #e74c3c;
                padding: 40px;
                background-color: #fdf2f2;
                border: 2px solid #e74c3c;
                border-radius: 8px;
                font-size: 11px;
            }
        """)
    
    def show_warning(self, message):
        """Show warning message"""
        self.loading_label.setText(f"警告: {message}")
        self.loading_label.setStyleSheet("""
            QLabel {
                color: #f39c12;
                padding: 40px;
                background-color: #fef9e7;
                border: 2px solid #f39c12;
                border-radius: 8px;
                font-size: 11px;
            }
        """)
    
    def cleanup_switchboard_processes(self):
        """Clean up Switchboard-related processes"""
        try:
            self.logger.info("Starting Switchboard process cleanup...")
            
            # Use subprocess.CREATE_NO_WINDOW to hide CMD windows
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
                                
        except Exception as e:
            self.logger.error(f"Error cleaning up Switchboard processes: {e}")
    
    def closeEvent(self, event):
        """Handle close event"""
        self.logger.info("SwitchboardWidget closing, cleaning up...")
        
        # Clean up Switchboard processes
        self.cleanup_switchboard_processes()
        
        # Clean up Switchboard dialog if it exists
        if self.switchboard_dialog:
            try:
                if hasattr(self.switchboard_dialog, 'on_exit'):
                    self.switchboard_dialog.on_exit()
            except Exception as e:
                self.logger.error(f"Error cleaning up Switchboard dialog: {e}")
        
        event.accept() 