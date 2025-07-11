# -*- coding: utf-8 -*-
"""
Main Window UI
Main window for the Switchboard MultiUser File Monitor application
"""

import sys
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QComboBox, QPushButton, QTextEdit, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QCheckBox, QMessageBox, QFileDialog, QStatusBar, QTabWidget,
    QDialog
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QIcon

from core.config_detector import ConfigDetector, SwitchboardConfig
from core.file_monitor import FileMonitor, MultiUserSession
from core.file_manager import FileManager, CopyOperation
from ui.session_widget import SessionWidget
from ui.file_tree_widget import FileTreeWidget
from ui.copy_dialog import CopyDialog
from utils.logger import get_logger

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
        __version__ = "1.1.0"


class ConfigDetectorWorker(QThread):
    """Worker thread for config detection to avoid UI blocking"""
    
    # Signals
    configs_found = Signal(list)  # List of config paths
    current_config_found = Signal(object)  # SwitchboardConfig or None
    fallback_config_found = Signal(object)  # SwitchboardConfig or None
    detection_completed = Signal()
    error_occurred = Signal(str)
    
    def __init__(self, config_detector: ConfigDetector):
        super().__init__()
        self.config_detector = config_detector
        self.logger = get_logger(__name__)
    
    def run(self):
        """Run config detection in background"""
        try:
            self.logger.debug("Starting config detection in background thread")
            
            # Get available configs
            configs = self.config_detector.get_available_configs()
            self.configs_found.emit(configs)
            
            # Try to detect current config
            current_config = self.config_detector.detect_current_config()
            self.current_config_found.emit(current_config)
            
            if not current_config and not configs:
                # No configs available, try fallback
                if not self.config_detector.is_switchboard_available():
                    fallback_config = self.config_detector.get_fallback_config()
                    self.fallback_config_found.emit(fallback_config)
                else:
                    self.fallback_config_found.emit(None)
            
            self.detection_completed.emit()
            self.logger.debug("Config detection completed successfully")
            
        except Exception as e:
            self.logger.error(f"Error in config detection thread: {e}")
            self.error_occurred.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__name__)
        
        # Initialize components
        self.config_detector = ConfigDetector()
        self.file_monitor: Optional[FileMonitor] = None
        self.file_manager = FileManager()
        self.current_config: Optional[SwitchboardConfig] = None
        self.current_session: Optional[MultiUserSession] = None
        self.sessions = {}
        self.config_worker: Optional[ConfigDetectorWorker] = None
        
        # Initialize state flags
        self._detecting_config = False
        self._monitoring_started = False
        
        # Setup UI
        self.setup_ui()
        self.setup_connections()
        
        # Start initial detection
        self.detect_config()
        
    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Switchboard MultiUser File Monitor")
        self.setMinimumSize(1200, 800)
        
        # Set window icon
        icon_path = Path(__file__).parent / "images" / "switchboard.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create toolbar
        toolbar_layout = self.create_toolbar()
        main_layout.addLayout(toolbar_layout)
        
        # Create splitter for main content
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left panel - Config and Sessions
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - File details and actions
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([400, 800])
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Remove the separator by setting custom style
        self.status_bar.setStyleSheet("QStatusBar::item { border: 0px; }")
        
        # Progress bar for status bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Version label (right side)
        self.version_label = QLabel(f"v{__version__}")
        self.version_label.setStyleSheet("QLabel { color: #888; font-size: 10px; }")
        self.status_bar.addPermanentWidget(self.version_label)
        
        # Status label (left side)
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)
        
    def create_toolbar(self) -> QHBoxLayout:
        """Create toolbar with main actions"""
        toolbar_layout = QHBoxLayout()
        
        # Config selection
        config_label = QLabel("Config:")
        config_label.setFont(QFont("Arial", 10, QFont.Bold))
        toolbar_layout.addWidget(config_label)
        
        self.config_combo = QComboBox()
        self.config_combo.setMinimumWidth(300)
        toolbar_layout.addWidget(self.config_combo)
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh Config")
        self.refresh_btn.setToolTip("Refresh configuration detection")
        # Add refresh icon
        refresh_icon_path = Path(__file__).parent / "images" / "icon_refresh.png"
        if refresh_icon_path.exists():
            self.refresh_btn.setIcon(QIcon(str(refresh_icon_path)))
        toolbar_layout.addWidget(self.refresh_btn)
        
        # Force refresh button
        self.force_refresh_btn = QPushButton("Force Refresh")
        self.force_refresh_btn.setToolTip("Force immediate scan of all sessions")
        # Add refresh icon
        if refresh_icon_path.exists():
            self.force_refresh_btn.setIcon(QIcon(str(refresh_icon_path)))
        toolbar_layout.addWidget(self.force_refresh_btn)
        
        # Auto-refresh checkbox
        self.auto_refresh_cb = QCheckBox("Auto Refresh")
        self.auto_refresh_cb.setChecked(True)
        self.auto_refresh_cb.setToolTip("Automatically refresh sessions every 5 seconds")
        toolbar_layout.addWidget(self.auto_refresh_cb)
        
        toolbar_layout.addStretch()
        
        # Copy buttons
        self.copy_all_btn = QPushButton("Copy All Sessions")
        self.copy_all_btn.setEnabled(False)
        self.copy_all_btn.setToolTip("Copy all session files to project content directory")
        # Add copy icon to copy buttons
        copy_icon_path = Path(__file__).parent / "images" / "copy_icon.png"
        if copy_icon_path.exists():
            copy_icon = QIcon(str(copy_icon_path))
            self.copy_all_btn.setIcon(copy_icon)
        toolbar_layout.addWidget(self.copy_all_btn)
        
        self.copy_current_btn = QPushButton("Copy Current Session")
        self.copy_current_btn.setEnabled(False)
        self.copy_current_btn.setToolTip("Copy current selected session files to project content directory")
        if copy_icon_path.exists():
            self.copy_current_btn.setIcon(copy_icon)
        toolbar_layout.addWidget(self.copy_current_btn)
        
        return toolbar_layout
    
    def create_left_panel(self) -> QWidget:
        """Create left panel with config info and sessions"""
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Config info group
        config_group = QGroupBox("Configuration Info")
        config_layout = QVBoxLayout(config_group)
        
        self.config_info_text = QTextEdit()
        # self.config_info_text.setMaximumHeight(80)
        self.config_info_text.setReadOnly(True)
        config_layout.addWidget(self.config_info_text)
        
        left_layout.addWidget(config_group)
        
        # Sessions group
        sessions_group = QGroupBox("MultiUser Sessions")
        sessions_layout = QVBoxLayout(sessions_group)
        
        self.session_widget = SessionWidget()
        sessions_layout.addWidget(self.session_widget)
        
        left_layout.addWidget(sessions_group)
        
        return left_widget
    
    def create_right_panel(self) -> QWidget:
        """Create right panel with file details and actions"""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Create tab widget
        tab_widget = QTabWidget()
        
        # File tree tab
        file_tree_tab = QWidget()
        file_tree_layout = QVBoxLayout(file_tree_tab)
        
        self.file_tree_widget = FileTreeWidget()
        file_tree_layout.addWidget(self.file_tree_widget)
        
        # File actions
        file_actions_layout = QHBoxLayout()
        
        self.copy_selected_btn = QPushButton("Copy Selected")
        self.copy_selected_btn.setEnabled(False)
        self.copy_selected_btn.setToolTip("Copy selected files to project content directory")
        # Add copy icon to copy selected button
        copy_icon_path = Path(__file__).parent / "images" / "copy_icon.png"
        if copy_icon_path.exists():
            self.copy_selected_btn.setIcon(QIcon(str(copy_icon_path)))
        file_actions_layout.addWidget(self.copy_selected_btn)
        
        self.open_folder_btn = QPushButton("Open Folder")
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.setToolTip("Open session folder in file explorer")
        file_actions_layout.addWidget(self.open_folder_btn)
        
        file_actions_layout.addStretch()
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setToolTip("Select all files")
        file_actions_layout.addWidget(self.select_all_btn)
        
        self.clear_selection_btn = QPushButton("Clear Selection")
        self.clear_selection_btn.setToolTip("Clear file selection")
        file_actions_layout.addWidget(self.clear_selection_btn)
        
        file_tree_layout.addLayout(file_actions_layout)
        
        tab_widget.addTab(file_tree_tab, "Files")
        
        # Log tab
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier", 9))
        log_layout.addWidget(self.log_text)
        
        tab_widget.addTab(log_tab, "Log")
        
        right_layout.addWidget(tab_widget)
        
        return right_widget
    
    def setup_connections(self):
        """Setup signal connections"""
        # Config combo
        self.config_combo.currentTextChanged.connect(self.on_config_changed)
        
        # Buttons
        self.refresh_btn.clicked.connect(self.detect_config)
        self.force_refresh_btn.clicked.connect(self.force_refresh_sessions)
        self.copy_all_btn.clicked.connect(self.copy_all_sessions)
        self.copy_current_btn.clicked.connect(self.copy_current_session)
        self.copy_selected_btn.clicked.connect(self.copy_selected_files)
        self.open_folder_btn.clicked.connect(self.open_session_folder)
        self.select_all_btn.clicked.connect(self.file_tree_widget.select_all)
        self.clear_selection_btn.clicked.connect(self.file_tree_widget.clear_selection)
        
        # Session widget
        self.session_widget.session_selected.connect(self.on_session_selected)
        self.session_widget.session_double_clicked.connect(self.on_session_double_clicked)
        self.session_widget.session_copy_requested.connect(self.copy_session_files)
        self.session_widget.session_delete_requested.connect(self.on_session_delete_requested)
        
        # File tree widget
        self.file_tree_widget.selection_changed.connect(self.on_file_selection_changed)
        
        # File manager
        self.file_manager.copy_progress.connect(self.on_copy_progress)
        self.file_manager.copy_completed.connect(self.on_copy_completed)
        self.file_manager.copy_error.connect(self.on_copy_error)
        
        # Auto refresh timer
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.refresh_sessions)
        self.auto_refresh_cb.toggled.connect(self.toggle_auto_refresh)
        self.toggle_auto_refresh(True)
    
    def detect_config(self):
        """Detect and load Switchboard configuration"""
        # Prevent multiple detection attempts
        if hasattr(self, '_detecting_config') and self._detecting_config:
            self.logger.debug("Config detection already in progress, skipping")
            return
        
        self._detecting_config = True
        
        self.status_label.setText("Detecting configuration...")
        self.refresh_btn.setEnabled(False)  # Disable button during detection
        self.refresh_btn.setText("Detecting...")
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        # Stop any existing config worker
        if self.config_worker and self.config_worker.isRunning():
            self.config_worker.quit()
            self.config_worker.wait()
        
        # Create and start config detection worker
        self.config_worker = ConfigDetectorWorker(self.config_detector)
        self.config_worker.configs_found.connect(self.on_configs_found)
        self.config_worker.current_config_found.connect(self.on_current_config_found)
        self.config_worker.fallback_config_found.connect(self.on_fallback_config_found)
        self.config_worker.detection_completed.connect(self.on_detection_completed)
        self.config_worker.error_occurred.connect(self.on_detection_error)
        
        self.config_worker.start()
        self.log_message("Starting configuration detection...")
    
    def on_configs_found(self, configs: list):
        """Handle configs found signal"""
        # Update combo box with found configs
        self.config_combo.clear()
        for config_path in configs:
            self.config_combo.addItem(str(config_path.stem), config_path)
        
        self.logger.debug(f"Found {len(configs)} configuration files")
    
    def on_current_config_found(self, current_config: SwitchboardConfig):
        """Handle current config found signal"""
        if current_config:
            self.load_config(current_config)
            self.log_message(f"Loaded current config: {current_config.project_name}")
        else:
            # If no current config, try to load first available config
            if self.config_combo.count() > 0:
                config_path = self.config_combo.itemData(0)
                if config_path:
                    first_config = self.config_detector.load_config_by_path(config_path)
                    if first_config:
                        self.load_config(first_config)
                        self.log_message(f"Loaded first available config: {first_config.project_name}")
                        return  # Prevent further processing
            
            # If no config could be loaded, this will be handled by fallback
    
    def on_fallback_config_found(self, fallback_config: SwitchboardConfig):
        """Handle fallback config found signal"""
        if fallback_config:
            self.load_config(fallback_config)
            self.config_combo.addItem("Fallback Configuration", None)
            self.config_combo.setCurrentIndex(0)
            self.log_message("Warning: Using fallback configuration. Some features may be limited.")
        else:
            self.log_message("Error: No configuration available. Please check your Switchboard installation.")
            self.status_label.setText("No configuration available")
    
    def on_detection_completed(self):
        """Handle detection completed signal"""
        self._detecting_config = False  # Reset detection flag
        
        self.refresh_btn.setEnabled(True)  # Re-enable button
        self.refresh_btn.setText("Refresh Config")  # Restore button text
        self.progress_bar.setVisible(False)  # Hide progress bar
        
        if self.current_config:
            self.status_label.setText("Ready")
            self.log_message("Configuration detection completed successfully")
        else:
            self.status_label.setText("Configuration error")
            self.log_message("No valid configuration found")
    
    def on_detection_error(self, error_message: str):
        """Handle detection error signal"""
        self._detecting_config = False  # Reset detection flag
        
        self.refresh_btn.setEnabled(True)  # Re-enable button
        self.refresh_btn.setText("Refresh Config")  # Restore button text
        self.progress_bar.setVisible(False)  # Hide progress bar
        self.status_label.setText("Detection failed")
        self.log_message(f"Configuration detection failed: {error_message}")
        self.logger.error(f"Config detection error: {error_message}")
    
    def load_config(self, config: SwitchboardConfig):
        """Load a specific configuration"""
        # Check if same config is already loaded
        if (self.current_config and 
            self.current_config.project_name == config.project_name and
            self.current_config.uproject_path == config.uproject_path):
            self.logger.debug(f"Config {config.project_name} already loaded, skipping")
            return
        
        self.current_config = config
        self.logger.info(f"Loaded config: {config.project_name}")
        
        # Reset monitoring flag to allow restart with new config
        self._monitoring_started = False
        
        # Update config info display
        self.update_config_info()
        
        # Start file monitoring
        self.start_file_monitoring()
        
        # Update UI state
        self.copy_all_btn.setEnabled(True)
        # Note: copy_current_btn is enabled when a session is selected
        
    def update_config_info(self):
        """Update configuration info display"""
        if not self.current_config:
            self.config_info_text.clear()
            return
        
        # Format paths to show only relevant parts
        project_name = self.current_config.project_name or "Unknown"
        
        # Simplify uproject path
        uproject_path = str(self.current_config.uproject_path) if self.current_config.uproject_path else "Not found"
        if len(uproject_path) > 50:
            uproject_path = "..." + uproject_path[-47:]
        
        # Simplify engine path
        engine_dir = str(self.current_config.engine_dir) if self.current_config.engine_dir else "Not found"
        if len(engine_dir) > 50:
            engine_dir = "..." + engine_dir[-47:]
        
        # Simplify config file path
        config_file = str(self.current_config.config_file_path) if self.current_config.config_file_path else "Fallback mode"
        if config_file != "Fallback mode" and len(config_file) > 50:
            config_file = "..." + config_file[-47:]
        
        # MultiUser server name
        server_name = self.current_config.multiuser_server_name or "Default"
        
        # Create clean, professional layout
        info = f"""PROJECT: {project_name}
ENGINE: {engine_dir}
SERVER: {server_name}
UPROJECT: {uproject_path}
CONFIG: {config_file}"""
        
        # Add warning if using fallback configuration (without emoji)
        if not self.current_config.config_file_path:
            info += "\n\nNOTE: Fallback configuration active"
            
        self.config_info_text.setText(info)
    
    def start_file_monitoring(self):
        """Start monitoring MultiUser files"""
        # Prevent multiple monitoring instances
        if hasattr(self, '_monitoring_started') and self._monitoring_started:
            self.logger.debug("File monitoring already started, skipping")
            return
        
        # Stop any existing monitor
        if self.file_monitor:
            self.file_monitor.stop()
            self.file_monitor.wait()
            self.file_monitor = None
        
        if not self.current_config:
            return
        
        # Reset current session when restarting monitoring
        self.current_session = None
        self.copy_current_btn.setEnabled(False)
        self.open_folder_btn.setEnabled(False)
        
        multiuser_path = self.current_config.get_multiuser_path()
        if not multiuser_path:
            self.logger.warning("No MultiUser path found in config")
            
            # Try to find MultiUser directories directly
            multiuser_paths = self.config_detector.get_active_sessions()
            if multiuser_paths:
                multiuser_path = multiuser_paths[0]
                self.logger.info(f"Using fallback MultiUser path: {multiuser_path}")
            else:
                self.logger.error("No MultiUser directories found")
                return
        
        if not multiuser_path.exists():
            self.logger.error(f"MultiUser path does not exist: {multiuser_path}")
            return
        
        self._monitoring_started = True
        
        self.file_monitor = FileMonitor(multiuser_path)
        self.file_monitor.session_found.connect(self.on_session_found)
        self.file_monitor.session_updated.connect(self.on_session_updated)
        self.file_monitor.session_removed.connect(self.on_session_removed)
        self.file_monitor.start()
        
        self.logger.info(f"Started monitoring: {multiuser_path}")
    
    def toggle_auto_refresh(self, enabled: bool):
        """Toggle auto refresh"""
        if enabled:
            self.auto_refresh_timer.start(2000)  # 2 seconds
        else:
            self.auto_refresh_timer.stop()
    
    def refresh_sessions(self):
        """Refresh sessions manually"""
        if self.file_monitor:
            self.file_monitor.scan_sessions()
    
    def force_refresh_sessions(self):
        """Force immediate refresh of all sessions"""
        if self.file_monitor:
            self.status_label.setText("Force refreshing...")
            self.file_monitor.scan_sessions()
            self.status_label.setText("Ready")
            self.log_message("Force refresh completed")
    
    def on_config_changed(self, config_name: str):
        """Handle config selection change"""
        if not config_name:
            return
        
        config_path = self.config_combo.currentData()
        if config_path:
            config = self.config_detector.load_config_by_path(config_path)
            if config:
                self.load_config(config)
    
    def on_session_found(self, session: MultiUserSession):
        """Handle new session found"""
        session_key = f"{session.session_id}_{session.user_id}"
        
        # Avoid duplicate sessions
        if session_key in self.sessions:
            self.logger.debug(f"Session {session_key} already exists, skipping duplicate")
            return
        
        self.sessions[session_key] = session
        self.session_widget.add_session(session)
        self.log_message(f"New session found: {session.session_id} (User: {session.user_id})")
    
    def on_session_updated(self, session: MultiUserSession):
        """Handle session updated"""
        session_key = f"{session.session_id}_{session.user_id}"
        self.sessions[session_key] = session
        self.session_widget.update_session(session)
        
        # If this is the currently selected session, refresh the file tree
        if hasattr(self, 'current_session') and self.current_session:
            current_session_key = f"{self.current_session.session_id}_{self.current_session.user_id}"
            if current_session_key == session_key:
                self.current_session = session
                self.file_tree_widget.load_session_files(session)
                self.log_message(f"Session updated & file tree refreshed: {session.session_id} (User: {session.user_id})")
            else:
                self.log_message(f"Session updated: {session.session_id} (User: {session.user_id})")
        else:
            self.log_message(f"Session updated: {session.session_id} (User: {session.user_id})")
    
    def on_session_removed(self, session_key: str):
        """Handle session removed"""
        if session_key in self.sessions:
            session = self.sessions[session_key]
            del self.sessions[session_key]
            self.session_widget.remove_session(session)
            self.log_message(f"Session removed: {session.session_id}")
            
            # If the removed session was the current session, disable related buttons
            if hasattr(self, 'current_session') and self.current_session:
                current_session_key = f"{self.current_session.session_id}_{self.current_session.user_id}"
                if current_session_key == session_key:
                    self.current_session = None
                    self.copy_current_btn.setEnabled(False)
                    self.open_folder_btn.setEnabled(False)
    
    def on_session_selected(self, session: MultiUserSession):
        """Handle session selection"""
        self.file_tree_widget.load_session_files(session)
        self.open_folder_btn.setEnabled(True)
        self.copy_current_btn.setEnabled(True)
        self.current_session = session
    
    def on_session_double_clicked(self, session: MultiUserSession):
        """Handle session double click - open folder instead of copying"""
        self.open_session_folder_by_session(session)
    
    def on_session_delete_requested(self, session: MultiUserSession):
        """Handle session deletion request"""
        import shutil
        
        session_key = f"{session.session_id}_{session.user_id}"
        
        try:
            # Delete the session folder
            if session.sandbox_path.exists():
                self.log_message(f"Deleting session folder: {session.sandbox_path}")
                shutil.rmtree(session.sandbox_path)
                self.log_message(f"Successfully deleted session folder")
            else:
                self.log_message(f"Session folder not found: {session.sandbox_path}")
            
            # Remove from sessions dictionary
            if session_key in self.sessions:
                del self.sessions[session_key]
                self.log_message(f"Removed session from monitoring: {session.session_id}")
            
            # Remove from session widget
            self.session_widget.remove_session(session)
            
            # If this was the current session, update UI state
            if hasattr(self, 'current_session') and self.current_session:
                current_session_key = f"{self.current_session.session_id}_{self.current_session.user_id}"
                if current_session_key == session_key:
                    self.current_session = None
                    self.copy_current_btn.setEnabled(False)
                    self.open_folder_btn.setEnabled(False)
                    self.file_tree_widget.clear()
                    self.log_message("Current session was deleted - UI state updated")
            
            # Show success message
            QMessageBox.information(
                self,
                "Session Deleted",
                f"Session successfully deleted!\n\n"
                f"Session ID: {session.session_id[:12]}...\n"
                f"Folder: {session.sandbox_path}"
            )
            
        except Exception as e:
            error_msg = f"Failed to delete session: {str(e)}"
            self.log_message(error_msg)
            self.logger.error(error_msg)
            QMessageBox.critical(
                self,
                "Delete Error",
                f"Failed to delete session!\n\n"
                f"Error: {str(e)}\n\n"
                f"You may need to close any applications using these files and try again."
            )
    
    def on_file_selection_changed(self, selected_files: list):
        """Handle file selection change"""
        self.copy_selected_btn.setEnabled(len(selected_files) > 0)
        
        # Update status
        if len(selected_files) > 0:
            self.status_label.setText(f"{len(selected_files)} files selected")
        else:
            self.status_label.setText("Ready")
    
    def copy_all_sessions(self):
        """Copy all session files"""
        if not self.current_config or not self.sessions:
            return
        
        content_dir = self.current_config.get_project_content_dir()
        if not content_dir:
            QMessageBox.warning(self, "Error", "No project content directory found")
            return
        
        # Show copy dialog
        dialog = CopyDialog(self.sessions.values(), content_dir, self)
        if dialog.exec() == QDialog.Accepted:
            self.log_message("Starting copy operation for all sessions...")
    
    def copy_current_session(self):
        """Copy current selected session files"""
        if not self.current_config or not hasattr(self, 'current_session') or not self.current_session:
            QMessageBox.warning(self, "Error", "No session selected")
            return
        
        content_dir = self.current_config.get_project_content_dir()
        if not content_dir:
            QMessageBox.warning(self, "Error", "No project content directory found")
            return
        
        # Show copy dialog for current session only
        dialog = CopyDialog([self.current_session], content_dir, self)
        if dialog.exec() == QDialog.Accepted:
            self.log_message(f"Starting copy operation for current session: {self.current_session.session_id}")
    
    def copy_selected_files(self):
        """Copy selected files"""
        selected_files = self.file_tree_widget.get_selected_files()
        if not selected_files or not self.current_config:
            return
        
        content_dir = self.current_config.get_project_content_dir()
        if not content_dir:
            QMessageBox.warning(self, "Error", "No project content directory found")
            return
        
        # Show file dialog to choose destination
        destination = QFileDialog.getExistingDirectory(
            self, "Choose Destination Directory", str(content_dir))
        
        if destination:
            destination_path = Path(destination)
            self.log_message(f"Starting copy operation for {len(selected_files)} files to {destination}")
            
            # Log selected files for debugging
            self.logger.debug(f"Selected files for copy:")
            for i, file_path in enumerate(selected_files):
                self.logger.debug(f"  {i+1}. {file_path}")
            
            try:
                # Get current session sandbox path for preserving directory structure
                session_sandbox_path = None
                if hasattr(self, 'current_session') and self.current_session:
                    session_sandbox_path = self.current_session.sandbox_path
                    self.log_message(f"Using session sandbox path: {session_sandbox_path}")
                else:
                    self.log_message("No active session, using common root detection")
                
                # Execute copy operation synchronously
                operations = self.file_manager.copy_selected_files(
                    selected_files, 
                    destination_path,
                    session_sandbox_path=session_sandbox_path
                )
                
                # Log detailed results
                successful = [op for op in operations if op.success]
                failed = [op for op in operations if not op.success]
                
                if successful:
                    self.log_message(f"Successfully copied {len(successful)} files:")
                    for op in successful:
                        self.log_message(f"  ✓ {op.source_path.name} -> {op.destination_path}")
                
                if failed:
                    self.log_message(f"Failed to copy {len(failed)} files:")
                    for op in failed:
                        self.log_message(f"  ✗ {op.source_path.name}: {op.error_message}")
                
                # Show summary message
                if len(failed) == 0:
                    QMessageBox.information(self, "Copy Complete", 
                        f"Successfully copied {len(successful)} files to {destination}")
                else:
                    QMessageBox.warning(self, "Copy Completed with Errors", 
                        f"Copied {len(successful)} files successfully, {len(failed)} files failed.\nCheck the log for details.")
                
            except Exception as e:
                error_msg = f"Copy operation failed: {str(e)}"
                self.log_message(error_msg)
                self.logger.error(error_msg)
                QMessageBox.critical(self, "Copy Error", error_msg)
    
    def copy_session_files(self, session: MultiUserSession):
        """Copy specific session files"""
        if not self.current_config:
            return
        
        content_dir = self.current_config.get_project_content_dir()
        if not content_dir:
            QMessageBox.warning(self, "Error", "No project content directory found")
            return
        
        self.file_manager.copy_session_to_content(session, content_dir)
        self.log_message(f"Copying session files: {session.session_id}")
    
    def open_session_folder_by_session(self, session: MultiUserSession):
        """Open specific session folder in file explorer"""
        import subprocess
        import platform
        
        folder_path = str(session.sandbox_path)
        
        try:
            if platform.system() == "Windows":
                subprocess.run(["explorer", folder_path])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", folder_path])
            elif platform.system() == "Linux":
                subprocess.run(["xdg-open", folder_path])
            
            self.log_message(f"Opened folder: {folder_path}")
            
        except Exception as e:
            error_msg = f"Failed to open folder: {e}"
            self.log_message(error_msg)
            self.logger.error(error_msg)
    
    def open_session_folder(self):
        """Open session folder in file explorer"""
        if hasattr(self, 'current_session') and self.current_session:
            import subprocess
            import platform
            
            folder_path = str(self.current_session.sandbox_path)
            
            if platform.system() == "Windows":
                subprocess.run(["explorer", folder_path])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", folder_path])
            elif platform.system() == "Linux":
                subprocess.run(["xdg-open", folder_path])
    
    def on_copy_progress(self, current: int, total: int):
        """Handle copy progress"""
        if total > 0:
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.status_label.setText(f"Copying files... {current}/{total}")
        else:
            self.progress_bar.setVisible(False)
            self.status_label.setText("Ready")
    
    def on_copy_completed(self, operations: list):
        """Handle copy completion"""
        self.progress_bar.setVisible(False)
        
        successful = [op for op in operations if op.success]
        failed = [op for op in operations if not op.success]
        
        message = f"Copy completed: {len(successful)} successful, {len(failed)} failed"
        self.status_label.setText(message)
        self.log_message(message)
        
        if failed:
            self.log_message("Failed operations:")
            for op in failed:
                self.log_message(f"  {op.source_path}: {op.error_message}")
    
    def on_copy_error(self, error_message: str):
        """Handle copy error"""
        self.progress_bar.setVisible(False)
        self.status_label.setText("Copy failed")
        self.log_message(f"Copy error: {error_message}")
        QMessageBox.critical(self, "Copy Error", error_message)
    
    def log_message(self, message: str):
        """Add message to log"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_text.append(formatted_message)
        self.logger.info(message)
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Reset flags
        self._monitoring_started = False
        self._detecting_config = False
        
        if self.file_monitor:
            self.file_monitor.stop()
            self.file_monitor.wait()
        
        if self.config_worker and self.config_worker.isRunning():
            self.config_worker.quit()
            self.config_worker.wait()
        
        self.auto_refresh_timer.stop()
        event.accept() 