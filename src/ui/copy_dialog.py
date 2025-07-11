# -*- coding: utf-8 -*-
"""
Copy Dialog
Dialog for copying session files with options and progress tracking
"""

from pathlib import Path
from typing import List, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QGroupBox, QListWidget, QListWidgetItem,
    QProgressBar, QTextEdit, QDialogButtonBox, QFileDialog,
    QMessageBox, QLineEdit, QFormLayout
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from core.file_monitor import MultiUserSession
from core.file_manager import FileManager, CopyOperation
from utils.logger import get_logger


class CopyWorker(QThread):
    """Worker thread for copying files"""
    
    progress_updated = Signal(int, int)  # current, total
    copy_completed = Signal(list)  # List[CopyOperation]
    error_occurred = Signal(str)
    
    def __init__(self, sessions: List[MultiUserSession], destination: Path, options: dict):
        super().__init__()
        self.sessions = sessions
        self.destination = destination
        self.options = options
        self.file_manager = FileManager()
        self.logger = get_logger(__name__)
        
    def run(self):
        """Run the copy operation"""
        try:
            all_operations = []
            total_sessions = len(self.sessions)
            
            for i, session in enumerate(self.sessions):
                self.progress_updated.emit(i, total_sessions)
                
                # Determine destination based on options
                if self.options.get('create_session_folders', False):
                    # Create session-specific destination
                    session_dest = self.destination / f"Session_{session.session_id[:8]}"
                else:
                    # Copy directly to content directory
                    session_dest = self.destination
                
                # Apply file filter if specified
                file_filter = None
                if self.options.get('filter_ue_assets', False):
                    file_filter = self.file_manager.is_ue_asset_file
                elif self.options.get('filter_config_files', False):
                    file_filter = self.file_manager.is_config_file
                elif self.options.get('filter_source_files', False):
                    file_filter = self.file_manager.is_source_file
                
                # Copy session files
                operations = self.file_manager.copy_session_to_content(
                    session, session_dest, file_filter
                )
                
                all_operations.extend(operations)
            
            self.progress_updated.emit(total_sessions, total_sessions)
            self.copy_completed.emit(all_operations)
            
        except Exception as e:
            self.logger.error(f"Copy operation failed: {e}")
            self.error_occurred.emit(str(e))


class CopyDialog(QDialog):
    """Dialog for copying session files"""
    
    def __init__(self, sessions: List[MultiUserSession], default_destination: Path, parent=None):
        super().__init__(parent)
        self.sessions = sessions
        self.default_destination = default_destination
        self.logger = get_logger(__name__)
        self.copy_worker: Optional[CopyWorker] = None
        
        self.setup_ui()
        self.setup_connections()
        self.update_session_list()
        
    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Copy Session Files")
        self.setMinimumSize(600, 500)
        
        main_layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("Copy MultiUser Session Files")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        main_layout.addWidget(title_label)
        
        # Sessions group
        sessions_group = QGroupBox("Sessions to Copy")
        sessions_layout = QVBoxLayout(sessions_group)
        
        self.session_list = QListWidget()
        self.session_list.setMaximumHeight(150)
        sessions_layout.addWidget(self.session_list)
        
        # Select all/none buttons
        select_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_none_btn = QPushButton("Select None")
        select_layout.addWidget(self.select_all_btn)
        select_layout.addWidget(self.select_none_btn)
        select_layout.addStretch()
        sessions_layout.addLayout(select_layout)
        
        main_layout.addWidget(sessions_group)
        
        # Destination group
        dest_group = QGroupBox("Destination")
        dest_layout = QFormLayout(dest_group)
        
        self.dest_edit = QLineEdit(str(self.default_destination))
        dest_layout.addRow("Destination:", self.dest_edit)
        
        self.browse_btn = QPushButton("Browse...")
        dest_layout.addRow("", self.browse_btn)
        
        main_layout.addWidget(dest_group)
        
        # Options group
        options_group = QGroupBox("Copy Options")
        options_layout = QVBoxLayout(options_group)
        
        self.preserve_structure_cb = QCheckBox("Preserve directory structure")
        self.preserve_structure_cb.setChecked(True)
        options_layout.addWidget(self.preserve_structure_cb)
        
        self.overwrite_cb = QCheckBox("Overwrite existing files")
        self.overwrite_cb.setChecked(True)
        options_layout.addWidget(self.overwrite_cb)
        
        self.create_session_folders_cb = QCheckBox("Create session folders")
        self.create_session_folders_cb.setChecked(False)  # Default to direct copy
        self.create_session_folders_cb.setToolTip("Create separate folders for each session (Session_XXXXX)")
        options_layout.addWidget(self.create_session_folders_cb)
        
        # File filters
        filter_layout = QHBoxLayout()
        self.filter_ue_assets_cb = QCheckBox("UE Assets only")
        self.filter_config_files_cb = QCheckBox("Config files only")
        self.filter_source_files_cb = QCheckBox("Source files only")
        
        filter_layout.addWidget(self.filter_ue_assets_cb)
        filter_layout.addWidget(self.filter_config_files_cb)
        filter_layout.addWidget(self.filter_source_files_cb)
        filter_layout.addStretch()
        
        options_layout.addLayout(filter_layout)
        
        main_layout.addWidget(options_group)
        
        # Progress group
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("Ready to copy")
        progress_layout.addWidget(self.progress_label)
        
        # Log
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(100)
        self.log_text.setReadOnly(True)
        self.log_text.setVisible(False)
        progress_layout.addWidget(self.log_text)
        
        main_layout.addWidget(progress_group)
        
        # Button box
        button_box = QDialogButtonBox()
        self.copy_btn = QPushButton("Start Copy")
        self.copy_btn.setDefault(True)
        self.cancel_btn = QPushButton("Cancel")
        self.close_btn = QPushButton("Close")
        self.close_btn.setVisible(False)
        
        button_box.addButton(self.copy_btn, QDialogButtonBox.AcceptRole)
        button_box.addButton(self.cancel_btn, QDialogButtonBox.RejectRole)
        button_box.addButton(self.close_btn, QDialogButtonBox.AcceptRole)
        
        main_layout.addWidget(button_box)
        
        self.button_box = button_box
        
    def setup_connections(self):
        """Setup signal connections"""
        self.select_all_btn.clicked.connect(self.select_all_sessions)
        self.select_none_btn.clicked.connect(self.select_no_sessions)
        self.browse_btn.clicked.connect(self.browse_destination)
        
        self.copy_btn.clicked.connect(self.start_copy)
        self.cancel_btn.clicked.connect(self.cancel_copy)
        self.close_btn.clicked.connect(self.accept)
        
        # Filter checkboxes - make them mutually exclusive
        self.filter_ue_assets_cb.toggled.connect(self.on_filter_changed)
        self.filter_config_files_cb.toggled.connect(self.on_filter_changed)
        self.filter_source_files_cb.toggled.connect(self.on_filter_changed)
        
    def update_session_list(self):
        """Update the session list"""
        self.session_list.clear()
        
        for session in self.sessions:
            item = QListWidgetItem()
            item.setText(f"{session.session_id[:12]}... - {session.file_count} files - {self._format_size(session.total_size)}")
            item.setData(Qt.UserRole, session)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.session_list.addItem(item)
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def select_all_sessions(self):
        """Select all sessions"""
        for i in range(self.session_list.count()):
            item = self.session_list.item(i)
            item.setCheckState(Qt.Checked)
    
    def select_no_sessions(self):
        """Select no sessions"""
        for i in range(self.session_list.count()):
            item = self.session_list.item(i)
            item.setCheckState(Qt.Unchecked)
    
    def browse_destination(self):
        """Browse for destination directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Destination Directory", self.dest_edit.text()
        )
        if directory:
            self.dest_edit.setText(directory)
    
    def on_filter_changed(self, checked: bool):
        """Handle filter checkbox changes"""
        if not checked:
            return
        
        # Make filters mutually exclusive
        sender = self.sender()
        if sender == self.filter_ue_assets_cb:
            self.filter_config_files_cb.setChecked(False)
            self.filter_source_files_cb.setChecked(False)
        elif sender == self.filter_config_files_cb:
            self.filter_ue_assets_cb.setChecked(False)
            self.filter_source_files_cb.setChecked(False)
        elif sender == self.filter_source_files_cb:
            self.filter_ue_assets_cb.setChecked(False)
            self.filter_config_files_cb.setChecked(False)
    
    def get_selected_sessions(self) -> List[MultiUserSession]:
        """Get selected sessions"""
        selected_sessions = []
        for i in range(self.session_list.count()):
            item = self.session_list.item(i)
            if item.checkState() == Qt.Checked:
                session = item.data(Qt.UserRole)
                selected_sessions.append(session)
        return selected_sessions
    
    def get_copy_options(self) -> dict:
        """Get copy options"""
        return {
            'preserve_structure': self.preserve_structure_cb.isChecked(),
            'overwrite': self.overwrite_cb.isChecked(),
            'create_session_folders': self.create_session_folders_cb.isChecked(),
            'filter_ue_assets': self.filter_ue_assets_cb.isChecked(),
            'filter_config_files': self.filter_config_files_cb.isChecked(),
            'filter_source_files': self.filter_source_files_cb.isChecked(),
        }
    
    def start_copy(self):
        """Start the copy operation"""
        # Validate inputs
        selected_sessions = self.get_selected_sessions()
        if not selected_sessions:
            QMessageBox.warning(self, "Warning", "Please select at least one session to copy.")
            return
        
        destination = Path(self.dest_edit.text())
        if not destination.exists():
            reply = QMessageBox.question(
                self, "Create Directory", 
                f"Destination directory does not exist:\n{destination}\n\nCreate it?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                try:
                    destination.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to create directory:\n{e}")
                    return
            else:
                return
        
        # Start copy operation
        self.copy_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log_text.setVisible(True)
        self.progress_label.setText("Starting copy operation...")
        
        # Create and start worker thread
        options = self.get_copy_options()
        self.copy_worker = CopyWorker(selected_sessions, destination, options)
        self.copy_worker.progress_updated.connect(self.on_progress_updated)
        self.copy_worker.copy_completed.connect(self.on_copy_completed)
        self.copy_worker.error_occurred.connect(self.on_copy_error)
        self.copy_worker.start()
        
        self.log_message(f"Starting copy of {len(selected_sessions)} sessions to {destination}")
    
    def cancel_copy(self):
        """Cancel the copy operation"""
        if self.copy_worker and self.copy_worker.isRunning():
            self.copy_worker.terminate()
            self.copy_worker.wait()
            self.log_message("Copy operation cancelled")
            self.progress_label.setText("Copy cancelled")
        else:
            self.reject()
    
    def on_progress_updated(self, current: int, total: int):
        """Handle progress update"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"Copying session {current + 1} of {total}...")
    
    def on_copy_completed(self, operations: List[CopyOperation]):
        """Handle copy completion"""
        self.progress_bar.setVisible(False)
        self.copy_btn.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.close_btn.setVisible(True)
        
        successful = [op for op in operations if op.success]
        failed = [op for op in operations if not op.success]
        
        self.progress_label.setText(f"Copy completed: {len(successful)} successful, {len(failed)} failed")
        
        self.log_message(f"Copy operation completed!")
        self.log_message(f"Successfully copied: {len(successful)} files")
        
        if failed:
            self.log_message(f"Failed to copy: {len(failed)} files")
            for op in failed[:10]:  # Show first 10 failed operations
                self.log_message(f"  Failed: {op.source_path.name} - {op.error_message}")
            
            if len(failed) > 10:
                self.log_message(f"  ... and {len(failed) - 10} more failed operations")
        
        # If copy was successful, proceed with additional steps
        if successful:
            self.log_message("Starting additional copy to Sandbox directory...")
            self._copy_to_sandbox_and_sync(successful)
        
        # Show summary dialog
        if failed:
            QMessageBox.warning(
                self, "Copy Completed with Errors",
                f"Copy completed with some errors.\n\n"
                f"Successfully copied: {len(successful)} files\n"
                f"Failed to copy: {len(failed)} files\n\n"
                f"Check the log for details."
            )
        else:
            QMessageBox.information(
                self, "Copy Completed",
                f"All files copied successfully!\n\n"
                f"Total files: {len(successful)}"
            )
    
    def _copy_to_sandbox_and_sync(self, successful_operations: List[CopyOperation]):
        """Copy files to Sandbox directory and execute sync_sandbox.bat"""
        import subprocess
        import shutil
        import sys
        import tempfile
        
        try:
            # Get project root directory (parent of Content directory)
            destination_path = Path(self.dest_edit.text())
            project_root = destination_path.parent
            sandbox_dir = project_root / "Sandbox"
            
            self.log_message(f"Project root: {project_root}")
            self.log_message(f"Sandbox directory: {sandbox_dir}")
            
            # Clear existing Sandbox directory if it exists
            if sandbox_dir.exists():
                self.log_message("Clearing existing Sandbox directory...")
                try:
                    shutil.rmtree(sandbox_dir)
                    self.log_message("Successfully cleared existing Sandbox directory")
                except Exception as e:
                    self.log_message(f"Warning: Could not fully clear Sandbox directory: {e}")
                    # Continue anyway - we'll try to overwrite files
            
            # Create Sandbox directory
            sandbox_dir.mkdir(parents=True, exist_ok=True)
            self.log_message(f"Sandbox directory created: {sandbox_dir}")
            
            # Copy files to Sandbox directory
            sandbox_copy_count = 0
            for operation in successful_operations:
                try:
                    # Get relative path from Content directory
                    relative_path = operation.destination_path.relative_to(destination_path)
                    sandbox_dest = sandbox_dir / relative_path
                    
                    # Create parent directories if needed
                    sandbox_dest.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copy the file
                    shutil.copy2(operation.destination_path, sandbox_dest)
                    sandbox_copy_count += 1
                    
                    self.log_message(f"Copied to Sandbox: {relative_path}")
                    
                except Exception as e:
                    self.log_message(f"Failed to copy to Sandbox: {operation.destination_path.name} - {e}")
            
            self.log_message(f"Successfully copied {sandbox_copy_count} files to Sandbox")
            
            # Get sync script from application resources
            sync_script_path = self._get_sync_script_path()
            
            if sync_script_path and sync_script_path.exists():
                self.log_message(f"Found sync script: {sync_script_path}")
                
                # Copy sync script to project root if it's from resources
                project_sync_script = project_root / "sync_sandbox.bat"
                if sync_script_path != project_sync_script:
                    shutil.copy2(sync_script_path, project_sync_script)
                    self.log_message(f"Copied sync script to project root")
                    sync_script_to_execute = project_sync_script
                else:
                    sync_script_to_execute = sync_script_path
                
                try:
                    # Change to project root directory for script execution
                    result = subprocess.run(
                        str(sync_script_to_execute),
                        cwd=str(project_root),
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=300  # 5 minute timeout
                    )
                    
                    if result.returncode == 0:
                        self.log_message("Sync script executed successfully!")
                        if result.stdout:
                            # Split output into lines and log each line
                            for line in result.stdout.strip().split('\n'):
                                if line.strip():
                                    self.log_message(f"Script: {line.strip()}")
                    else:
                        self.log_message(f"Sync script failed with return code: {result.returncode}")
                        if result.stderr:
                            for line in result.stderr.strip().split('\n'):
                                if line.strip():
                                    self.log_message(f"Script Error: {line.strip()}")
                    
                except subprocess.TimeoutExpired:
                    self.log_message("Sync script timed out after 5 minutes")
                except Exception as e:
                    self.log_message(f"Failed to execute sync script: {e}")
            else:
                self.log_message("Sync script not found in application resources")
                
        except Exception as e:
            self.log_message(f"Error in sandbox copy and sync: {e}")
            self.logger.error(f"Error in sandbox copy and sync: {e}")
    
    def _get_sync_script_path(self) -> Optional[Path]:
        """Get the path to sync_sandbox.bat from application resources"""
        import sys
        
        # Check if running as PyInstaller bundle
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running as PyInstaller bundle - get from temporary directory
            bundle_dir = Path(sys._MEIPASS)
            sync_script = bundle_dir / "external" / "sync_sandbox.bat"
            self.log_message(f"Looking for script in bundle: {sync_script}")
            return sync_script if sync_script.exists() else None
        else:
            # Running as Python script - get from source directory
            # Get the directory containing this file
            current_dir = Path(__file__).parent
            # Go up to src directory, then to external
            src_dir = current_dir.parent
            sync_script = src_dir / "external" / "sync_sandbox.bat"
            self.log_message(f"Looking for script in source: {sync_script}")
            return sync_script if sync_script.exists() else None
    
    def on_copy_error(self, error_message: str):
        """Handle copy error"""
        self.progress_bar.setVisible(False)
        self.copy_btn.setEnabled(True)
        self.progress_label.setText("Copy failed")
        
        self.log_message(f"Copy operation failed: {error_message}")
        
        QMessageBox.critical(self, "Copy Error", f"Copy operation failed:\n{error_message}")
    
    def log_message(self, message: str):
        """Add message to log"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_text.append(formatted_message)
        self.logger.info(message)
    
    def closeEvent(self, event):
        """Handle close event"""
        if self.copy_worker and self.copy_worker.isRunning():
            reply = QMessageBox.question(
                self, "Copy in Progress",
                "Copy operation is still in progress. Do you want to cancel it?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.copy_worker.terminate()
                self.copy_worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept() 