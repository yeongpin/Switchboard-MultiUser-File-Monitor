# -*- coding: utf-8 -*-
"""
SVN Version Control Widget
Manages SVN version control for Unreal project Content folders
"""

import os
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTextEdit, QTreeWidget, QTreeWidgetItem, QGroupBox,
    QProgressBar, QMessageBox, QSplitter, QHeaderView, QComboBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QIcon, QColor

from utils.logger import get_logger


class SVNWorker(QThread):
    """Worker thread for SVN operations"""
    
    # Signals
    svn_status_updated = Signal(list)  # List of SVN status items
    svn_log_updated = Signal(list)     # List of SVN log entries
    operation_completed = Signal(str, bool)  # Message, success
    progress_updated = Signal(int, int)  # Current, total
    
    def __init__(self, content_path: Path):
        super().__init__()
        self.content_path = content_path
        self.logger = get_logger(__name__)
        self.current_operation = None
        
    def run(self):
        """Run SVN operations"""
        try:
            if self.current_operation == "status":
                self._get_svn_status()
            elif self.current_operation == "log":
                self._get_svn_log()
            elif self.current_operation == "update":
                self._svn_update()
            elif self.current_operation == "commit":
                self._svn_commit()
        except Exception as e:
            self.logger.error(f"SVN operation failed: {e}")
            self.operation_completed.emit(f"操作失败: {str(e)}", False)
    
    def _get_svn_status(self):
        """Get SVN status"""
        try:
            result = subprocess.run(
                ['svn', 'status', '--xml'],
                cwd=self.content_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Parse XML output and emit status
                status_items = self._parse_svn_status_xml(result.stdout)
                self.svn_status_updated.emit(status_items)
                self.operation_completed.emit("Status update completed", True)
            else:
                self.logger.error(f"SVN status failed: {result.stderr}")
                self.operation_completed.emit(f"Failed to get status: {result.stderr}", False)
                
        except subprocess.TimeoutExpired:
            self.operation_completed.emit("Operation timeout", False)
        except FileNotFoundError:
            self.operation_completed.emit("SVN command not found, please ensure SVN is installed", False)
    
    def _get_svn_log(self):
        """Get SVN log"""
        try:
            result = subprocess.run(
                ['svn', 'log', '--xml', '-l', '50'],  # Last 50 entries
                cwd=self.content_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                log_entries = self._parse_svn_log_xml(result.stdout)
                self.svn_log_updated.emit(log_entries)
                self.operation_completed.emit("Log update completed", True)
            else:
                self.logger.error(f"SVN log failed: {result.stderr}")
                self.operation_completed.emit(f"Failed to get log: {result.stderr}", False)
                
        except subprocess.TimeoutExpired:
            self.operation_completed.emit("Operation timeout", False)
        except FileNotFoundError:
            self.operation_completed.emit("SVN command not found, please ensure SVN is installed", False)
    
    def _svn_update(self):
        """SVN update"""
        try:
            result = subprocess.run(
                ['svn', 'update'],
                cwd=self.content_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                self.operation_completed.emit("Update completed", True)
            else:
                self.logger.error(f"SVN update failed: {result.stderr}")
                self.operation_completed.emit(f"Update failed: {result.stderr}", False)
                
        except subprocess.TimeoutExpired:
            self.operation_completed.emit("Update timeout", False)
        except FileNotFoundError:
            self.operation_completed.emit("SVN command not found, please ensure SVN is installed", False)
    
    def _svn_commit(self, message: str = "Auto commit from Switchboard"):
        """SVN commit"""
        try:
            result = subprocess.run(
                ['svn', 'commit', '-m', message],
                cwd=self.content_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                self.operation_completed.emit("Commit completed", True)
            else:
                self.logger.error(f"SVN commit failed: {result.stderr}")
                self.operation_completed.emit(f"Commit failed: {result.stderr}", False)
                
        except subprocess.TimeoutExpired:
            self.operation_completed.emit("Commit timeout", False)
        except FileNotFoundError:
            self.operation_completed.emit("SVN command not found, please ensure SVN is installed", False)
    
    def _parse_svn_status_xml(self, xml_output: str) -> List[Dict[str, Any]]:
        """Parse SVN status XML output"""
        # Simple XML parsing for status
        status_items = []
        lines = xml_output.split('\n')
        
        for line in lines:
            if '<entry' in line and 'path=' in line:
                # Extract path and status
                import re
                path_match = re.search(r'path="([^"]+)"', line)
                status_match = re.search(r'item="([^"]+)"', line)
                
                if path_match and status_match:
                    status_items.append({
                        'path': path_match.group(1),
                        'status': status_match.group(1),
                        'file': Path(path_match.group(1)).name
                    })
        
        return status_items
    
    def _parse_svn_log_xml(self, xml_output: str) -> List[Dict[str, Any]]:
        """Parse SVN log XML output"""
        # Simple XML parsing for log
        log_entries = []
        lines = xml_output.split('\n')
        
        current_entry = {}
        for line in lines:
            if '<logentry' in line:
                current_entry = {}
                revision_match = re.search(r'revision="([^"]+)"', line)
                if revision_match:
                    current_entry['revision'] = revision_match.group(1)
            elif '<author>' in line:
                author = line.replace('<author>', '').replace('</author>', '').strip()
                current_entry['author'] = author
            elif '<date>' in line:
                date = line.replace('<date>', '').replace('</date>', '').strip()
                current_entry['date'] = date
            elif '<msg>' in line:
                msg = line.replace('<msg>', '').replace('</msg>', '').strip()
                current_entry['message'] = msg
            elif '</logentry>' in line:
                if current_entry:
                    log_entries.append(current_entry)
        
        return log_entries


class SVNWidget(QWidget):
    """SVN Version Control Widget"""
    
    def __init__(self, content_path: Optional[Path] = None):
        super().__init__()
        self.logger = get_logger(__name__)
        self.content_path = content_path
        self.svn_worker = None
        
        self.setup_ui()
        self.setup_connections()
        
        if self.content_path:
            self.update_content_path(self.content_path)
    
    def detect_config(self):
        """Detect and load Switchboard configuration"""
        try:
            from core.config_detector import ConfigDetector
            self.config_detector = ConfigDetector()
            
            # Get available configs
            configs = self.config_detector.get_available_configs()
            self.on_configs_found(configs)
            
            # Try to detect current config
            current_config = self.config_detector.detect_current_config()
            self.on_current_config_found(current_config)
            
            self.log_message("Configuration detection completed", "S")
            
        except Exception as e:
            self.logger.error(f"Config detection failed: {e}")
            self.log_message(f"Configuration detection failed: {str(e)}", "E")
    
    def force_refresh_config(self):
        """Force refresh configuration"""
        self.log_message("Force refreshing configuration...", "I")
        self.detect_config()
    
    def on_configs_found(self, configs: list):
        """Handle configs found"""
        # Update combo box with found configs
        self.config_combo.clear()
        for config_path in configs:
            self.config_combo.addItem(str(config_path.stem), config_path)
        
        self.logger.debug(f"Found {len(configs)} configuration files")
    
    def on_current_config_found(self, current_config):
        """Handle current config found"""
        if current_config:
            self.load_config(current_config)
            self.log_message(f"Loaded configuration: {current_config.project_name}", "S")
        else:
            self.log_message("No current configuration found", "W")
    
    def on_config_changed(self, config_name: str):
        """Handle config selection change"""
        if not config_name:
            return
        
        config_path = self.config_combo.currentData()
        if config_path:
            config = self.config_detector.load_config_by_path(config_path)
            if config:
                self.load_config(config)
    
    def load_config(self, config):
        """Load a specific configuration"""
        try:
            content_path = config.get_project_content_dir()
            if content_path and content_path.exists():
                self.update_content_path(content_path)
                self.log_message(f"Content path updated: {content_path}", "S")
            else:
                self.log_message("No valid Content directory found in configuration", "W")
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            self.log_message(f"Failed to load configuration: {str(e)}", "E")
    
    def try_get_content_path(self):
        """Try to get content path from config detector"""
        # This method is now handled by detect_config()
        pass
    
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Create toolbar
        toolbar_layout = self.create_toolbar()
        layout.addLayout(toolbar_layout)
        
        # Create file status area
        file_widget = self.create_file_status_area()
        layout.addWidget(file_widget)
        
        # Create log area
        log_widget = self.create_log_area()
        layout.addWidget(log_widget)
    
    def create_toolbar(self) -> QHBoxLayout:
        """Create toolbar with config and controls"""
        toolbar_layout = QHBoxLayout()
        
        # Config selection
        config_label = QLabel("Config:")
        config_label.setFont(QFont("Arial", 10, QFont.Bold))
        toolbar_layout.addWidget(config_label)
        
        self.config_combo = QComboBox()
        self.config_combo.setMinimumWidth(300)
        toolbar_layout.addWidget(self.config_combo)
        
        # Refresh button
        self.refresh_config_btn = QPushButton("Refresh Config")
        self.refresh_config_btn.setToolTip("Refresh configuration detection")
        # Add refresh icon
        refresh_icon_path = Path(__file__).parent.parent / "multiusersync" / "images" / "icon_refresh.png"
        if not refresh_icon_path.exists():
            # Try alternative paths for packaged environment
            import sys
            if getattr(sys, 'frozen', False):
                # Running in a bundle (PyInstaller)
                base_path = Path(sys._MEIPASS)
                refresh_icon_path = base_path / "ui" / "multiusersync" / "images" / "icon_refresh.png"
            else:
                # Running in normal Python environment
                refresh_icon_path = Path(__file__).parent.parent / "multiusersync" / "images" / "icon_refresh.png"
        
        if refresh_icon_path.exists():
            self.refresh_config_btn.setIcon(QIcon(str(refresh_icon_path)))
        toolbar_layout.addWidget(self.refresh_config_btn)
        
        # Force refresh button
        self.force_refresh_config_btn = QPushButton("Force Refresh")
        self.force_refresh_config_btn.setToolTip("Force immediate scan of all configurations")
        # Add refresh icon
        if refresh_icon_path.exists():
            self.force_refresh_config_btn.setIcon(QIcon(str(refresh_icon_path)))
        toolbar_layout.addWidget(self.force_refresh_config_btn)
        
        toolbar_layout.addStretch()
        
        # Content path display
        path_label = QLabel("Content Path:")
        path_label.setFont(QFont("Arial", 10, QFont.Bold))
        toolbar_layout.addWidget(path_label)
        
        self.path_label = QLabel("Not set")
        self.path_label.setStyleSheet("QLabel { color: #cccccc; font-size: 10px; }")
        toolbar_layout.addWidget(self.path_label)
        
        return toolbar_layout
    
    def create_file_status_area(self) -> QWidget:
        """Create file status area with controls and tree"""
        file_widget = QWidget()
        file_layout = QVBoxLayout(file_widget)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Refresh Status")
        self.refresh_btn.setToolTip("Refresh SVN Status")
        control_layout.addWidget(self.refresh_btn)
        
        self.update_btn = QPushButton("Update")
        self.update_btn.setToolTip("SVN Update")
        control_layout.addWidget(self.update_btn)
        
        self.commit_btn = QPushButton("Commit")
        self.commit_btn.setToolTip("SVN Commit")
        control_layout.addWidget(self.commit_btn)
        
        self.log_btn = QPushButton("View Log")
        self.log_btn.setToolTip("View SVN Log")
        control_layout.addWidget(self.log_btn)
        
        control_layout.addStretch()
        file_layout.addLayout(control_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        file_layout.addWidget(self.progress_bar)
        
        # Status tree
        status_group = QGroupBox("File Status")
        status_layout = QVBoxLayout(status_group)
        
        self.status_tree = QTreeWidget()
        self.status_tree.setHeaderLabels(["File", "Status", "Path"])
        self.status_tree.setAlternatingRowColors(True)
        header = self.status_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        
        status_layout.addWidget(self.status_tree)
        file_layout.addWidget(status_group)
        
        return file_widget
    
    def create_log_area(self) -> QWidget:
        """Create log area"""
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        
        # Log area
        log_group = QGroupBox("Operation Log")
        log_group_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier", 9))
        log_group_layout.addWidget(self.log_text)
        
        log_layout.addWidget(log_group)
        
        return log_widget
    
    def setup_connections(self):
        """Setup signal connections"""
        # Config connections
        self.config_combo.currentTextChanged.connect(self.on_config_changed)
        self.refresh_config_btn.clicked.connect(self.detect_config)
        self.force_refresh_config_btn.clicked.connect(self.force_refresh_config)
        
        # SVN connections
        self.refresh_btn.clicked.connect(self.refresh_status)
        self.update_btn.clicked.connect(self.svn_update)
        self.commit_btn.clicked.connect(self.svn_commit)
        self.log_btn.clicked.connect(self.view_log)
        
        # Start initial config detection
        self.detect_config()
    
    def update_content_path(self, content_path: Path):
        """Update the content path"""
        self.content_path = content_path
        self.path_label.setText(str(content_path))
        self.log_message(f"Content path set: {content_path}", "S")
        
        # Check if this is an SVN repository
        self.check_svn_repository()
    
    def check_svn_repository(self):
        """Check if the content path is an SVN repository"""
        if not self.content_path:
            return
        
        svn_dir = self.content_path / ".svn"
        if svn_dir.exists():
            self.log_message("SVN repository detected", "S")
            self.refresh_status()
        else:
            self.log_message("Warning: SVN repository not detected (.svn directory does not exist)", "W")
    
    def refresh_status(self):
        """Refresh SVN status"""
        if not self.content_path:
            self.log_message("Error: Content path not set", "E")
            return
        
        self.start_svn_operation("status")
    
    def svn_update(self):
        """SVN update"""
        if not self.content_path:
            self.log_message("Error: Content path not set", "E")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Update", 
            "Are you sure you want to perform SVN Update?\nThis will update all files to the latest version.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.start_svn_operation("update")
    
    def svn_commit(self):
        """SVN commit"""
        if not self.content_path:
            self.log_message("Error: Content path not set", "E")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Commit", 
            "Are you sure you want to perform SVN Commit?\nThis will commit all changes.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.start_svn_operation("commit")
    
    def view_log(self):
        """View SVN log"""
        if not self.content_path:
            self.log_message("Error: Content path not set", "E")
            return
        
        self.start_svn_operation("log")
    
    def start_svn_operation(self, operation: str):
        """Start an SVN operation"""
        if self.svn_worker and self.svn_worker.isRunning():
            self.log_message("Operation in progress, please wait...", "W")
            return
        
        self.svn_worker = SVNWorker(self.content_path)
        self.svn_worker.current_operation = operation
        
        # Connect signals
        self.svn_worker.svn_status_updated.connect(self.on_status_updated)
        self.svn_worker.svn_log_updated.connect(self.on_log_updated)
        self.svn_worker.operation_completed.connect(self.on_operation_completed)
        self.svn_worker.progress_updated.connect(self.on_progress_updated)
        
        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        # Disable buttons
        self.refresh_btn.setEnabled(False)
        self.update_btn.setEnabled(False)
        self.commit_btn.setEnabled(False)
        self.log_btn.setEnabled(False)
        
        # Start operation
        self.svn_worker.start()
        self.log_message(f"Starting operation: {operation}", "I")
    
    def on_status_updated(self, status_items: List[Dict[str, Any]]):
        """Handle SVN status update"""
        self.status_tree.clear()
        
        for item in status_items:
            tree_item = QTreeWidgetItem([
                item['file'],
                item['status'],
                item['path']
            ])
            
            # Set color based on status
            status = item['status']
            if status == 'modified':
                tree_item.setForeground(1, QColor('#ffa500'))  # Orange
            elif status == 'added':
                tree_item.setForeground(1, QColor('#00ff00'))  # Green
            elif status == 'deleted':
                tree_item.setForeground(1, QColor('#ff0000'))  # Red
            elif status == 'conflicted':
                tree_item.setForeground(1, QColor('#ff00ff'))  # Magenta
            
            self.status_tree.addTopLevelItem(tree_item)
        
        self.log_message(f"Status update completed, {len(status_items)} files", "S")
    
    def on_log_updated(self, log_entries: List[Dict[str, Any]]):
        """Handle SVN log update"""
        log_text = "SVN 日志:\n" + "="*50 + "\n\n"
        
        for entry in log_entries:
            log_text += f"版本: {entry.get('revision', 'N/A')}\n"
            log_text += f"作者: {entry.get('author', 'N/A')}\n"
            log_text += f"日期: {entry.get('date', 'N/A')}\n"
            log_text += f"消息: {entry.get('message', 'N/A')}\n"
            log_text += "-"*30 + "\n"
        
        self.log_text.setText(log_text)
        self.log_message(f"Log update completed, {len(log_entries)} entries", "S")
    
    def on_operation_completed(self, message: str, success: bool):
        """Handle operation completion"""
        self.progress_bar.setVisible(False)
        
        # Re-enable buttons
        self.refresh_btn.setEnabled(True)
        self.update_btn.setEnabled(True)
        self.commit_btn.setEnabled(True)
        self.log_btn.setEnabled(True)
        
        if success:
            self.log_message(f"✓ {message}", "S")
        else:
            self.log_message(f"✗ {message}", "E")
    
    def on_progress_updated(self, current: int, total: int):
        """Handle progress update"""
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
    
    def log_message(self, message: str, level: str = "I"):
        """Add message to log with color coding"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color coding based on level
        if level == "D":  # Debug
            color = "#888888"
        elif level == "I":  # Info
            color = "#ffffff"
        elif level == "S":  # Success
            color = "#00ff00"
        elif level == "W":  # Warning
            color = "#ffff00"
        elif level == "E":  # Error
            color = "#ff0000"
        else:
            color = "#ffffff"
        
        formatted_message = f'<span style="color: #cccccc;">[{timestamp}] [{level}]</span> <span style="color: {color};">{message}</span>'
        
        # Add to log text using HTML
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
        self.log_text.insertHtml(formatted_message + "<br>")
        
        # Scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # Also log to file
        self.logger.info(f"SVN: {message}") 