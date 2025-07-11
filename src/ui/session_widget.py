# -*- coding: utf-8 -*-
"""
Session Widget
Displays MultiUser sessions in a table format
"""

from typing import List, Optional
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMenu
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QColor, QBrush, QFont, QIcon

from core.file_monitor import MultiUserSession
from utils.logger import get_logger


class SessionWidget(QWidget):
    """Widget for displaying MultiUser sessions"""
    
    # Signals
    session_selected = Signal(MultiUserSession)
    session_double_clicked = Signal(MultiUserSession)
    session_copy_requested = Signal(MultiUserSession)
    session_delete_requested = Signal(MultiUserSession)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self.sessions = {}  # session_key -> (session, row_index)
        
        # Load status icons
        self.load_status_icons()
        
        self.setup_ui()
        self.setup_connections()
    
    def load_status_icons(self):
        """Load status icons from images folder"""
        self.status_icons = {}
        images_path = Path(__file__).parent / "images"
        
        icon_files = {
            "active": "status_green.png",
            "inactive": "status_red.png",
            "warning": "status_orange.png",
            "idle": "status_cyan.png",
            "blank": "status_blank.png",
            "disabled": "status_blank_disabled.png"
        }
        
        for status, filename in icon_files.items():
            icon_path = images_path / filename
            if icon_path.exists():
                self.status_icons[status] = QIcon(str(icon_path))
            else:
                self.status_icons[status] = QIcon()  # Empty icon as fallback
    
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        
        # Create table widget
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Session ID", "User ID", "Last Modified", "Files", "Size", "Status"
        ])
        
        # Configure table
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)  # Disable editing
        
        # Configure headers
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.Interactive)  # Session ID
        header.setSectionResizeMode(1, QHeaderView.Interactive)  # User ID
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Last Modified
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Files
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Size
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Status
        
        # Set column widths
        self.table.setColumnWidth(0, 200)  # Session ID
        self.table.setColumnWidth(1, 200)  # User ID
        
        layout.addWidget(self.table)
        
        # Enable context menu
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
    
    def setup_connections(self):
        """Setup signal connections"""
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
    
    def add_session(self, session: MultiUserSession):
        """Add a new session to the table"""
        session_key = f"{session.session_id}_{session.user_id}"
        
        if session_key in self.sessions:
            # Update existing session
            self.update_session(session)
            return
        
        # Add new row
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Store session reference
        self.sessions[session_key] = (session, row)
        
        # Populate row
        self._populate_row(row, session)
        
        self.logger.debug(f"Added session to table: {session_key}")
    
    def update_session(self, session: MultiUserSession):
        """Update existing session in the table"""
        session_key = f"{session.session_id}_{session.user_id}"
        
        if session_key not in self.sessions:
            self.add_session(session)
            return
        
        stored_session, row = self.sessions[session_key]
        
        # Update session reference
        self.sessions[session_key] = (session, row)
        
        # Update row data
        self._populate_row(row, session)
        
        self.logger.debug(f"Updated session in table: {session_key}")
    
    def remove_session(self, session: MultiUserSession):
        """Remove session from the table"""
        session_key = f"{session.session_id}_{session.user_id}"
        
        if session_key not in self.sessions:
            return
        
        _, row = self.sessions[session_key]
        
        # Remove row
        self.table.removeRow(row)
        
        # Update row indices for remaining sessions
        for key, (sess, sess_row) in self.sessions.items():
            if sess_row > row:
                self.sessions[key] = (sess, sess_row - 1)
        
        # Remove from sessions dict
        del self.sessions[session_key]
        
        self.logger.debug(f"Removed session from table: {session_key}")
    
    def _populate_row(self, row: int, session: MultiUserSession):
        """Populate a table row with session data"""
        # Session ID (truncated for display)
        session_id_item = QTableWidgetItem(session.session_id[:12] + "...")
        session_id_item.setToolTip(session.session_id)
        session_id_item.setData(Qt.UserRole, session)
        self.table.setItem(row, 0, session_id_item)
        
        # User ID (truncated for display)
        user_id_item = QTableWidgetItem(session.user_id[:12] + "...")
        user_id_item.setToolTip(session.user_id)
        self.table.setItem(row, 1, user_id_item)
        
        # Last Modified
        last_modified_item = QTableWidgetItem(
            session.last_modified.strftime("%Y-%m-%d %H:%M:%S")
        )
        self.table.setItem(row, 2, last_modified_item)
        
        # File count
        file_count_item = QTableWidgetItem(str(session.file_count))
        self.table.setItem(row, 3, file_count_item)
        
        # Size
        size_item = QTableWidgetItem(self._format_size(session.total_size))
        self.table.setItem(row, 4, size_item)
        
        # Status with icon
        status_text, status_icon_key = self._get_session_status(session)
        status_item = QTableWidgetItem(status_text)
        
        # Set status icon
        if status_icon_key in self.status_icons:
            status_item.setIcon(self.status_icons[status_icon_key])
        
        self.table.setItem(row, 5, status_item)
        
        # Highlight recently modified sessions
        if self._is_recent_session(session):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
    
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
    
    def _is_recent_session(self, session: MultiUserSession) -> bool:
        """Check if session was modified recently (within last 2 minutes)"""
        from datetime import datetime, timedelta
        return (datetime.now() - session.last_modified) < timedelta(minutes=2)
    
    def _get_session_status(self, session: MultiUserSession) -> tuple[str, str]:
        """Get session status text and icon key"""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        time_diff = now - session.last_modified
        
        # Active: modified within last 2 minutes (very recent)
        if time_diff < timedelta(minutes=2):
            return "Active", "active"
        
        # Idle: modified within last 10 minutes (recent)
        elif time_diff < timedelta(minutes=10):
            return "Idle", "idle"
        
        # Warning: modified within last 30 minutes (somewhat recent)
        elif time_diff < timedelta(minutes=30):
            return "Warning", "warning"
        
        # Inactive: older than 30 minutes
        else:
            return "Inactive", "inactive"
    
    def on_selection_changed(self):
        """Handle selection change"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            item = self.table.item(current_row, 0)
            if item:
                session = item.data(Qt.UserRole)
                if session:
                    self.session_selected.emit(session)
    
    def on_item_double_clicked(self, item: QTableWidgetItem):
        """Handle item double click"""
        session = item.data(Qt.UserRole)
        if session:
            self.session_double_clicked.emit(session)
    
    def show_context_menu(self, position: QPoint):
        """Show context menu"""
        item = self.table.itemAt(position)
        if not item:
            return
        
        session = item.data(Qt.UserRole)
        if not session:
            return
        
        menu = QMenu(self)
        
        # Copy session action
        copy_action = menu.addAction("Copy Session Files")
        copy_action.triggered.connect(lambda: self.session_copy_requested.emit(session))
        
        # Open folder action
        open_action = menu.addAction("Open Folder")
        open_action.triggered.connect(lambda: self.open_session_folder(session))
        
        # Show session info action
        info_action = menu.addAction("Show Session Info")
        info_action.triggered.connect(lambda: self.show_session_info(session))
        
        # Add separator
        menu.addSeparator()
        
        # Delete session action with warning emoji
        delete_action = menu.addAction("Delete Session (Permanent)")
        delete_action.triggered.connect(lambda: self.request_delete_session(session))
        
        menu.exec(self.table.mapToGlobal(position))
    
    def open_session_folder(self, session: MultiUserSession):
        """Open session folder in file explorer"""
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
        except Exception as e:
            self.logger.error(f"Failed to open folder: {e}")
    
    def show_session_info(self, session: MultiUserSession):
        """Show detailed session information"""
        from PySide6.QtWidgets import QMessageBox
        
        info_text = f"""Session Information:
        
Session ID: {session.session_id}
User ID: {session.user_id}
Last Modified: {session.last_modified.strftime("%Y-%m-%d %H:%M:%S")}
File Count: {session.file_count}
Total Size: {self._format_size(session.total_size)}
Sandbox Path: {session.sandbox_path}"""
        
        QMessageBox.information(self, "Session Info", info_text)
    
    def request_delete_session(self, session: MultiUserSession):
        """Request deletion of a session with confirmation"""
        from PySide6.QtWidgets import QMessageBox
        
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Delete Session",
            f"Are you sure you want to delete this session?\n\n"
            f"Session ID: {session.session_id[:12]}...\n"
            f"User ID: {session.user_id[:12]}...\n"
            f"Files: {session.file_count}\n"
            f"Size: {self._format_size(session.total_size)}\n\n"
            f"⚠️ This will permanently delete all session files and folders!\n\n"
            f"Path: {session.sandbox_path}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.logger.info(f"User confirmed deletion of session: {session.session_id}")
            self.session_delete_requested.emit(session)
        else:
            self.logger.info(f"User cancelled deletion of session: {session.session_id}")
    
    def get_selected_session(self) -> Optional[MultiUserSession]:
        """Get currently selected session"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            item = self.table.item(current_row, 0)
            if item:
                return item.data(Qt.UserRole)
        return None
    
    def get_all_sessions(self) -> List[MultiUserSession]:
        """Get all sessions"""
        return [session for session, _ in self.sessions.values()]
    
    def clear_sessions(self):
        """Clear all sessions"""
        self.table.setRowCount(0)
        self.sessions.clear()
        self.logger.debug("Cleared all sessions from table") 