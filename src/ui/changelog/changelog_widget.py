# -*- coding: utf-8 -*-
"""
Changelog Widget
Displays version history with expandable/collapsible sections
"""

import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QPushButton, QLabel, QScrollArea, QFrame, QGroupBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor

from utils.logger import get_logger


class ChangelogWidget(QWidget):
    """Widget for displaying changelog with expandable sections"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__name__)
        self.changelog_data = []
        self.setup_ui()
        self.load_changelog()
        
    def setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Scroll area for changelog content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Content widget
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.setSpacing(2)
        
        scroll_area.setWidget(self.content_widget)
        layout.addWidget(scroll_area)
        
    def load_changelog(self):
        """Load and parse changelog.md file"""
        try:
            # Try to find changelog.md file
            changelog_path = None
            
            # Check if running in packaged environment
            import sys
            if getattr(sys, 'frozen', False):
                # Running in a bundle (PyInstaller)
                base_path = Path(sys._MEIPASS)
                changelog_path = base_path / "ui" / "changelog" / "CHANGELOG.md"
                self.logger.info(f"PyInstaller environment detected. Looking for: {changelog_path}")
            else:
                # Running in development environment
                # Try multiple possible locations
                possible_paths = [
                    Path(__file__).parent / "CHANGELOG.md",  # src/ui/changelog/CHANGELOG.md
                    Path(__file__).parent.parent.parent.parent / "CHANGELOG.md",  # Project root
                    Path(__file__).parent.parent.parent / "CHANGELOG.md",  # src/CHANGELOG.md
                ]
                
                changelog_path = None
                for path in possible_paths:
                    if path.exists():
                        changelog_path = path
                        break
                
                self.logger.info(f"Development environment. Tried paths: {[str(p) for p in possible_paths]}")
                self.logger.info(f"Found changelog at: {changelog_path}")
            
            # Try to read the file
            if changelog_path and changelog_path.exists():
                try:
                    with open(changelog_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self.parse_changelog(content)
                    self.logger.info(f"Changelog loaded successfully from: {changelog_path}")
                except Exception as e:
                    self.logger.error(f"Failed to read changelog file: {e}")
                    self.show_error(f"无法读取changelog文件: {changelog_path}")
            else:
                self.logger.warning(f"Changelog file not found at: {changelog_path}")
                self.show_error("找不到 CHANGELOG.md 文件")
                
        except Exception as e:
            self.show_error(f"加载changelog失败: {str(e)}")
            self.logger.error(f"Failed to load changelog: {e}")
    

    
    def parse_changelog(self, content):
        """Parse changelog content and create UI elements"""
        lines = content.split('\n')
        current_version = None
        current_date = None
        current_items = []
        version_count = 0
        
        for line in lines:
            line = line.strip()
            
            # Check for version header (### v1.x.x)
            if line.startswith('### v'):
                # Save previous version if exists
                if current_version:
                    is_latest = version_count == 0
                    self.create_version_section(current_version, current_date, current_items, is_latest)
                    version_count += 1
                
                # Start new version
                current_version = line[4:]  # Remove "### "
                current_date = None
                current_items = []
                
            # Check for date (#### YYYY/MM/DD)
            elif line.startswith('#### ') and '/' in line:
                current_date = line[5:]  # Remove "#### "
                
            # Check for list items (- item)
            elif line.startswith('- ') and current_version:
                current_items.append(line[2:])  # Remove "- "
        
        # Add the last version
        if current_version:
            is_latest = version_count == 0
            self.create_version_section(current_version, current_date, current_items, is_latest)
    
    def create_version_section(self, version, date, items, is_latest=False):
        """Create a collapsible section for a version"""
        # Create version card frame
        version_frame = QFrame()
        version_frame.setStyleSheet("""
            QFrame {
                background-color: #3d3d3d;
                border: none;
                border-radius: 4px;
                margin: 1px 0px;
            }
        """)
        
        # Main layout for the card
        card_layout = QVBoxLayout(version_frame)
        card_layout.setContentsMargins(15, 12, 15, 12)
        card_layout.setSpacing(0)
        
        # Header with version, date, and toggle button
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        
        # Version label
        version_label = QLabel(version)
        version_font = QFont("Arial", 11, QFont.Bold)
        version_label.setFont(version_font)
        version_label.setStyleSheet("color: #ffffff;")
        header_layout.addWidget(version_label)
        
        header_layout.addStretch()
        
        # Date label
        if date:
            date_label = QLabel(date)
            date_label.setStyleSheet("color: #cccccc; font-size: 10px;")
            header_layout.addWidget(date_label)
        
        # Toggle button
        toggle_btn = QPushButton("▼")
        toggle_btn.setFixedSize(16, 16)
        toggle_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                font-size: 9px;
                color: #666666;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #c5c5c5;
            }
        """)
        header_layout.addWidget(toggle_btn)
        
        card_layout.addLayout(header_layout)
        
        # Content area (initially hidden)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(5,5,5,5)
        content_layout.setSpacing(6)
        content_widget.setStyleSheet("""
            QWidget {
                background-color: #242424;
            }
        """)
        
        # Add items
        for item in items:
            item_label = QLabel(f"• {item}")
            item_label.setWordWrap(True)
            item_label.setStyleSheet("""
                QLabel {
                    color: #ffffff;
                    font-size: 10px;
                    line-height: 1.4;
                    background-color: transparent;
                    border: none;
                    padding: 5px;
                }
            """)
            content_layout.addWidget(item_label)
        
        content_layout.addStretch()
        card_layout.addWidget(content_widget)
        
        # Check if this is the latest version and expand it by default
        if is_latest:
            # Show content and update button for latest version
            content_widget.show()
            toggle_btn.setText("▲")
        else:
            # Hide content for older versions
            content_widget.hide()
        
        # Connect toggle button
        toggle_btn.clicked.connect(lambda checked, widget=content_widget, btn=toggle_btn: self.toggle_content(widget, btn))
        
        # Add to main layout
        self.content_layout.addWidget(version_frame)
    
    def toggle_content(self, content_widget, button):
        """Toggle content visibility"""
        if content_widget.isVisible():
            content_widget.hide()
            button.setText("▼")
        else:
            content_widget.show()
            button.setText("▲")
    
    def show_error(self, message):
        """Show error message"""
        error_label = QLabel(message)
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setStyleSheet("color: #d9534f; font-size: 10px; margin: 20px; background-color: #3e3e42; padding: 10px; border-radius: 4px;")
        self.content_layout.addWidget(error_label)
        self.logger.error(f"Changelog error: {message}") 