# -*- coding: utf-8 -*-
"""
File Tree Widget
Displays session files in a tree structure with checkboxes for selection
"""

import os
from pathlib import Path
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QCheckBox, QHBoxLayout, QLabel, QMenu
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QIcon, QPixmap

from core.file_monitor import MultiUserSession
from utils.logger import get_logger


class FileTreeWidget(QWidget):
    """Widget for displaying session files in a tree structure"""
    
    # Signals
    selection_changed = Signal(list)  # List of selected file paths
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self.current_session: Optional[MultiUserSession] = None
        self.file_items = {}  # file_path -> QTreeWidgetItem
        
        self.setup_ui()
        self.setup_connections()
    
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        
        # Info bar
        info_layout = QHBoxLayout()
        self.info_label = QLabel("No session selected")
        self.info_label.setStyleSheet("color: gray; font-style: italic;")
        info_layout.addWidget(self.info_label)
        info_layout.addStretch()
        
        # Selection summary
        self.selection_label = QLabel("0 files selected")
        self.selection_label.setStyleSheet("color: blue; font-weight: bold;")
        info_layout.addWidget(self.selection_label)
        
        layout.addLayout(info_layout)
        
        # Create tree widget
        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["File", "Size", "Modified", "Type"])
        
        # Configure tree
        self.tree.setRootIsDecorated(True)
        self.tree.setSortingEnabled(True)
        self.tree.setAlternatingRowColors(True)
        
        # Configure headers
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # File - takes remaining space
        header.setSectionResizeMode(1, QHeaderView.Interactive)  # Size - user can resize
        header.setSectionResizeMode(2, QHeaderView.Interactive)  # Modified - user can resize
        header.setSectionResizeMode(3, QHeaderView.Interactive)  # Type - user can resize
        
        # Set initial column widths
        self.tree.setColumnWidth(0, 300)  # File
        self.tree.setColumnWidth(1, 80)   # Size
        self.tree.setColumnWidth(2, 150)  # Modified
        self.tree.setColumnWidth(3, 100)  # Type
        
        # Enable double-click on header to auto-resize columns
        header.setStretchLastSection(False)
        header.sectionDoubleClicked.connect(self.auto_resize_column)
        
        layout.addWidget(self.tree)
        
        # Enable context menu
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
    
    def setup_connections(self):
        """Setup signal connections"""
        self.tree.itemChanged.connect(self.on_item_changed)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
    
    def auto_resize_column(self, logical_index: int):
        """Auto-resize column to fit contents"""
        if logical_index == 0:  # File column - don't auto-resize since it's set to Stretch
            return
        
        # Temporarily change resize mode to ResizeToContents
        header = self.tree.header()
        original_mode = header.sectionResizeMode(logical_index)
        header.setSectionResizeMode(logical_index, QHeaderView.ResizeToContents)
        
        # Get the optimal width
        optimal_width = header.sectionSize(logical_index)
        
        # Restore original resize mode
        header.setSectionResizeMode(logical_index, original_mode)
        
        # Set the optimal width
        self.tree.setColumnWidth(logical_index, optimal_width)
        
        self.logger.debug(f"Auto-resized column {logical_index} to width {optimal_width}")
    
    def reset_column_widths(self):
        """Reset column widths to default values"""
        self.tree.setColumnWidth(0, 300)  # File
        self.tree.setColumnWidth(1, 80)   # Size
        self.tree.setColumnWidth(2, 150)  # Modified
        self.tree.setColumnWidth(3, 100)  # Type
        
        self.logger.debug("Column widths reset to default values")
    
    def load_session_files(self, session: MultiUserSession):
        """Load files from a session"""
        self.current_session = session
        
        # Block signals during rebuild to prevent spurious events
        self.tree.blockSignals(True)
        
        # Clear all state
        self.file_items.clear()
        self.tree.clear()
        
        # Update info label
        self.info_label.setText(f"Session: {session.session_id[:12]}... - {session.file_count} files")
        self.info_label.setStyleSheet("color: white; font-weight: bold;")
        
        # Get all files in session
        try:
            files = []
            for root, dirs, file_names in os.walk(session.sandbox_path):
                for file_name in file_names:
                    file_path = Path(root) / file_name
                    files.append(file_path)
            
            # Build tree structure
            self._build_tree(files, session.sandbox_path)
            
            # Expand tree
            self.tree.expandAll()
            
            # Unblock signals
            self.tree.blockSignals(False)
            
            # Update selection count
            self.update_selection_count()
            
            # Log successful load
            self.logger.debug(f"Loaded {len(files)} files from session {session.session_id}")
            
        except Exception as e:
            self.logger.error(f"Error loading session files: {e}")
            self.info_label.setText(f"Error loading files: {str(e)}")
            self.info_label.setStyleSheet("color: red;")
            # Unblock signals even on error
            self.tree.blockSignals(False)
    
    def _build_tree(self, files: List[Path], base_path: Path):
        """Build tree structure from file list"""
        # Create directory structure
        dir_items = {}  # path -> QTreeWidgetItem
        
        for file_path in sorted(files):
            try:
                # Get relative path
                rel_path = file_path.relative_to(base_path)
                
                # Create directory items if needed
                current_parent = None
                current_path = Path()
                
                for part in rel_path.parts[:-1]:  # All parts except filename
                    current_path = current_path / part
                    
                    if current_path not in dir_items:
                        # Create directory item
                        dir_item = QTreeWidgetItem()
                        dir_item.setText(0, part)
                        dir_item.setIcon(0, self._get_folder_icon())
                        dir_item.setFlags(dir_item.flags() | Qt.ItemIsUserCheckable)
                        dir_item.setCheckState(0, Qt.Unchecked)
                        dir_item.setData(0, Qt.UserRole, "directory")
                        
                        if current_parent:
                            current_parent.addChild(dir_item)
                        else:
                            self.tree.addTopLevelItem(dir_item)
                        
                        dir_items[current_path] = dir_item
                    
                    current_parent = dir_items[current_path]
                
                # Create file item
                file_item = QTreeWidgetItem()
                file_item.setText(0, rel_path.name)
                file_item.setIcon(0, self._get_file_icon(file_path))
                file_item.setFlags(file_item.flags() | Qt.ItemIsUserCheckable)
                file_item.setCheckState(0, Qt.Unchecked)
                file_item.setData(0, Qt.UserRole, str(file_path))
                
                # File size
                try:
                    size = file_path.stat().st_size
                    file_item.setText(1, self._format_size(size))
                except:
                    file_item.setText(1, "Unknown")
                
                # Modified time
                try:
                    mtime = file_path.stat().st_mtime
                    from datetime import datetime
                    mod_time = datetime.fromtimestamp(mtime)
                    file_item.setText(2, mod_time.strftime("%Y-%m-%d %H:%M:%S"))
                except:
                    file_item.setText(2, "Unknown")
                
                # File type
                file_item.setText(3, self._get_file_type(file_path))
                
                # Add to tree
                if current_parent:
                    current_parent.addChild(file_item)
                else:
                    self.tree.addTopLevelItem(file_item)
                
                # Store reference
                self.file_items[file_path] = file_item
                
            except Exception as e:
                self.logger.error(f"Error processing file {file_path}: {e}")
    
    def _get_folder_icon(self) -> QIcon:
        """Get folder icon"""
        # You can customize this to use actual icons
        return QIcon()  # Default folder icon
    
    def _get_file_icon(self, file_path: Path) -> QIcon:
        """Get file icon based on file type"""
        # You can customize this to use actual icons based on file extension
        return QIcon()  # Default file icon
    
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
    
    def _get_file_type(self, file_path: Path) -> str:
        """Get file type description"""
        extension = file_path.suffix.lower()
        
        type_map = {
            '.uasset': 'UE Asset',
            '.umap': 'UE Map',
            '.uexp': 'UE Export',
            '.ubulk': 'UE Bulk',
            '.uptnl': 'UE Thumbnail',
            '.ini': 'Configuration',
            '.json': 'JSON Data',
            '.txt': 'Text',
            '.log': 'Log File',
            '.cpp': 'C++ Source',
            '.h': 'C++ Header',
            '.cs': 'C# Source',
            '.py': 'Python',
            '.js': 'JavaScript',
            '.html': 'HTML',
            '.css': 'CSS',
            '.png': 'PNG Image',
            '.jpg': 'JPEG Image',
            '.jpeg': 'JPEG Image',
            '.bmp': 'BMP Image',
            '.tga': 'TGA Image',
            '.wav': 'WAV Audio',
            '.mp3': 'MP3 Audio',
            '.mp4': 'MP4 Video',
            '.avi': 'AVI Video',
            '.fbx': 'FBX Model',
            '.obj': 'OBJ Model',
            '.blend': 'Blender File',
            '.max': '3ds Max File',
            '.zip': 'ZIP Archive',
            '.rar': 'RAR Archive',
            '.7z': '7-Zip Archive',
        }
        
        return type_map.get(extension, extension.upper() + ' File' if extension else 'File')
    
    def on_item_changed(self, item: QTreeWidgetItem, column: int):
        """Handle item check state change"""
        if column == 0:  # Only handle changes to the first column (checkbox)
            # Block signals to prevent recursive updates
            self.tree.blockSignals(True)
            
            # Update child and parent items
            self._update_child_items(item)
            self._update_parent_items(item)
            
            # Unblock signals
            self.tree.blockSignals(False)
            
            # Update UI
            self.update_selection_count()
            
            # Emit selection changed signal
            selected_files = self.get_selected_files()
            self.selection_changed.emit(selected_files)
    
    def _update_child_items(self, item: QTreeWidgetItem):
        """Update child items when parent changes"""
        check_state = item.checkState(0)
        
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, check_state)
            self._update_child_items(child)  # Recursive
    
    def _update_parent_items(self, item: QTreeWidgetItem):
        """Update parent items when child changes"""
        parent = item.parent()
        if not parent:
            return
        
        # Count checked children
        checked_count = 0
        total_count = parent.childCount()
        
        for i in range(total_count):
            child = parent.child(i)
            if child.checkState(0) == Qt.Checked:
                checked_count += 1
        
        # Update parent check state
        if checked_count == 0:
            parent.setCheckState(0, Qt.Unchecked)
        elif checked_count == total_count:
            parent.setCheckState(0, Qt.Checked)
        else:
            parent.setCheckState(0, Qt.PartiallyChecked)
        
        # Recurse to parent's parent
        self._update_parent_items(parent)
    
    def _set_item_checked_recursive(self, item: QTreeWidgetItem, check_state: Qt.CheckState):
        """Recursively set item and all children to the specified check state"""
        item.setCheckState(0, check_state)
        
        # Recursively set children
        for i in range(item.childCount()):
            child = item.child(i)
            self._set_item_checked_recursive(child, check_state)
    
    def get_selected_files(self) -> List[Path]:
        """Get list of selected file paths"""
        selected_files = []
        
        # Check all items in the tree, not just file_items
        # This ensures we get all selected files even if tree structure changed
        def check_item(item):
            # Only include files (not directories)
            if item.checkState(0) == Qt.Checked:
                file_path_str = item.data(0, Qt.UserRole)
                if file_path_str and file_path_str != "directory":
                    try:
                        file_path = Path(file_path_str)
                        if file_path.exists():
                            selected_files.append(file_path)
                    except:
                        pass
            
            # Check children
            for i in range(item.childCount()):
                check_item(item.child(i))
        
        # Check all top-level items
        for i in range(self.tree.topLevelItemCount()):
            check_item(self.tree.topLevelItem(i))
        
        return selected_files
    
    def select_all(self):
        """Select all files"""
        # Block signals to prevent multiple updates
        self.tree.blockSignals(True)
        
        # Set all items to checked
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            self._set_item_checked_recursive(item, Qt.Checked)
        
        # Unblock signals and update
        self.tree.blockSignals(False)
        self.update_selection_count()
        
        # Emit selection changed signal
        selected_files = self.get_selected_files()
        self.selection_changed.emit(selected_files)
    
    def clear_selection(self):
        """Clear all selections"""
        # Block signals to prevent multiple updates
        self.tree.blockSignals(True)
        
        # Set all items to unchecked
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            self._set_item_checked_recursive(item, Qt.Unchecked)
        
        # Unblock signals and update
        self.tree.blockSignals(False)
        self.update_selection_count()
        
        # Emit selection changed signal
        selected_files = self.get_selected_files()
        self.selection_changed.emit(selected_files)
    
    def select_by_type(self, file_types: List[str]):
        """Select files by type"""
        # Block signals to prevent multiple updates
        self.tree.blockSignals(True)
        
        # First clear all selections
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            self._set_item_checked_recursive(item, Qt.Unchecked)
        
        # Then select files by type
        for file_path, item in self.file_items.items():
            if file_path.suffix.lower() in file_types:
                item.setCheckState(0, Qt.Checked)
                # Update parent items
                self._update_parent_items(item)
        
        # Unblock signals and update
        self.tree.blockSignals(False)
        self.update_selection_count()
        
        # Emit selection changed signal
        selected_files = self.get_selected_files()
        self.selection_changed.emit(selected_files)
    
    def update_selection_count(self):
        """Update selection count display"""
        selected_files = self.get_selected_files()
        selected_count = len(selected_files)
        total_count = len(self.file_items)
        
        if selected_count == 0:
            self.selection_label.setText(f"0 files selected")
            self.selection_label.setStyleSheet("color: gray;")
        else:
            self.selection_label.setText(f"{selected_count} of {total_count} files selected")
            self.selection_label.setStyleSheet("color: blue; font-weight: bold;")
        
        # Debug log
        if selected_count > 0:
            self.logger.debug(f"Selection updated: {selected_count} files selected")
    
    def show_context_menu(self, position: QPoint):
        """Show context menu"""
        item = self.tree.itemAt(position)
        if not item:
            return
        
        menu = QMenu(self)
        
        # Selection actions
        if item.checkState(0) == Qt.Checked:
            uncheck_action = menu.addAction("Uncheck")
            uncheck_action.triggered.connect(lambda: item.setCheckState(0, Qt.Unchecked))
        else:
            check_action = menu.addAction("Check")
            check_action.triggered.connect(lambda: item.setCheckState(0, Qt.Checked))
        
        menu.addSeparator()
        
        # Quick selection actions
        select_all_action = menu.addAction("Select All")
        select_all_action.triggered.connect(self.select_all)
        
        clear_all_action = menu.addAction("Clear All")
        clear_all_action.triggered.connect(self.clear_selection)
        
        menu.addSeparator()
        
        # Type-based selection
        type_menu = menu.addMenu("Select by Type")
        
        ue_assets_action = type_menu.addAction("UE Assets")
        ue_assets_action.triggered.connect(
            lambda: self.select_by_type(['.uasset', '.umap', '.uexp', '.ubulk', '.uptnl'])
        )
        
        config_action = type_menu.addAction("Config Files")
        config_action.triggered.connect(
            lambda: self.select_by_type(['.ini', '.json', '.cfg', '.config'])
        )
        
        source_action = type_menu.addAction("Source Files")
        source_action.triggered.connect(
            lambda: self.select_by_type(['.cpp', '.h', '.cs', '.py', '.js'])
        )
        
        # File info (if it's a file)
        file_path_str = item.data(0, Qt.UserRole)
        if file_path_str and file_path_str != "directory":
            menu.addSeparator()
            
            info_action = menu.addAction("Show File Info")
            info_action.triggered.connect(lambda: self.show_file_info(Path(file_path_str)))
        
        # Add separator for column actions
        menu.addSeparator()
        
        # Reset column widths
        reset_action = menu.addAction("🔄 Reset Column Widths")
        reset_action.triggered.connect(self.reset_column_widths)
        
        menu.exec(self.tree.mapToGlobal(position))
    
    def show_file_info(self, file_path: Path):
        """Show file information"""
        from PySide6.QtWidgets import QMessageBox
        
        try:
            stat = file_path.stat()
            from datetime import datetime
            
            info_text = f"""File Information:
            
Name: {file_path.name}
Path: {file_path}
Size: {self._format_size(stat.st_size)}
Modified: {datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")}
Type: {self._get_file_type(file_path)}"""
            
            QMessageBox.information(self, "File Info", info_text)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not get file info: {e}")
    
    def clear(self):
        """Clear the tree"""
        # Block signals during clear
        self.tree.blockSignals(True)
        
        # Clear all data
        self.tree.clear()
        self.file_items.clear()
        self.current_session = None
        
        # Unblock signals
        self.tree.blockSignals(False)
        
        # Update UI
        self.info_label.setText("No session selected")
        self.info_label.setStyleSheet("color: gray; font-style: italic;")
        self.selection_label.setText("0 files selected")
        self.selection_label.setStyleSheet("color: gray;") 