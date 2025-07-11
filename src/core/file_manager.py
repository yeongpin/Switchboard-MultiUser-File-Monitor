# -*- coding: utf-8 -*-
"""
File Manager Module
Handles copying files from MultiUser sessions to project content directory
"""

import os
import shutil
import time
from pathlib import Path
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from PySide6.QtCore import QThread, Signal
from utils.logger import get_logger
from core.file_monitor import MultiUserSession


@dataclass
class CopyOperation:
    """File copy operation result"""
    source_path: Path
    destination_path: Path
    success: bool
    error_message: Optional[str] = None
    file_size: int = 0
    
    def __str__(self):
        return f"Copy {self.source_path} -> {self.destination_path} ({'Success' if self.success else 'Failed'})"


class FileManager(QThread):
    """Manages file operations for MultiUser sessions"""
    
    # Signals
    copy_progress = Signal(int, int)  # current, total
    copy_completed = Signal(list)  # List[CopyOperation]
    copy_error = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__name__)
        self.copy_operations: List[CopyOperation] = []
        self.running = False
        
    def copy_session_to_content(
        self, 
        session: MultiUserSession, 
        content_dir: Path,
        file_filter: Optional[Callable[[Path], bool]] = None
    ) -> List[CopyOperation]:
        """Copy session files to content directory"""
        self.logger.info(f"Starting copy operation for session: {session.session_id}")
        
        operations = []
        
        try:
            # Get all files in the session
            session_files = self._get_session_files(session.sandbox_path)
            
            # Filter files if filter is provided
            if file_filter:
                session_files = [f for f in session_files if file_filter(f)]
            
            total_files = len(session_files)
            self.copy_progress.emit(0, total_files)
            
            for i, source_file in enumerate(session_files):
                try:
                    # Calculate relative path from sandbox
                    relative_path = source_file.relative_to(session.sandbox_path)
                    destination_file = content_dir / relative_path
                    
                    # Create destination directory if it doesn't exist
                    destination_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copy file
                    shutil.copy2(source_file, destination_file)
                    
                    operation = CopyOperation(
                        source_path=source_file,
                        destination_path=destination_file,
                        success=True,
                        file_size=source_file.stat().st_size
                    )
                    
                    self.logger.debug(f"Copied: {source_file} -> {destination_file}")
                    
                except Exception as e:
                    operation = CopyOperation(
                        source_path=source_file,
                        destination_path=destination_file if 'destination_file' in locals() else Path("Unknown"),
                        success=False,
                        error_message=str(e)
                    )
                    
                    self.logger.error(f"Failed to copy {source_file}: {e}")
                
                operations.append(operation)
                self.copy_progress.emit(i + 1, total_files)
            
            self.copy_completed.emit(operations)
            self.logger.info(f"Copy operation completed. {len([op for op in operations if op.success])} files copied successfully")
            
        except Exception as e:
            self.logger.error(f"Error during copy operation: {e}")
            self.copy_error.emit(str(e))
        
        return operations
    
    def copy_selected_files(
        self, 
        source_files: List[Path], 
        destination_dir: Path,
        session_sandbox_path: Optional[Path] = None,
        preserve_structure: bool = True
    ) -> List[CopyOperation]:
        """Copy selected files to destination directory"""
        self.logger.info(f"Starting copy operation for {len(source_files)} selected files to {destination_dir}")
        
        if session_sandbox_path:
            self.logger.info(f"Using session sandbox path for structure preservation: {session_sandbox_path}")
        else:
            self.logger.info("No session sandbox path provided, using common root detection")
        
        operations = []
        total_files = len(source_files)
        self.copy_progress.emit(0, total_files)
        
        # Log source files for debugging
        self.logger.debug("Source files:")
        for i, file_path in enumerate(source_files):
            self.logger.debug(f"  {i+1}. {file_path}")
        
        try:
            # Determine the base root for preserving structure
            base_root = None
            if preserve_structure:
                if session_sandbox_path and session_sandbox_path.exists():
                    # Use session sandbox path as base root to preserve full directory structure
                    base_root = session_sandbox_path
                    self.logger.debug(f"Using session sandbox as base root: {base_root}")
                else:
                    # Fallback to finding common root among selected files
                    base_root = self._find_common_root(source_files)
                    self.logger.debug(f"Using common root as base root: {base_root}")
            
            for i, source_file in enumerate(source_files):
                try:
                    # Check if source file exists
                    if not source_file.exists():
                        raise FileNotFoundError(f"Source file does not exist: {source_file}")
                    
                    # Calculate destination path
                    if preserve_structure and base_root:
                        try:
                            relative_path = source_file.relative_to(base_root)
                            destination_file = destination_dir / relative_path
                            self.logger.info(f"Preserving structure:")
                            self.logger.info(f"  Source: {source_file}")
                            self.logger.info(f"  Base root: {base_root}")
                            self.logger.info(f"  Relative path: {relative_path}")
                            self.logger.info(f"  Destination: {destination_file}")
                        except ValueError as e:
                            # If file is not within base_root, use filename only
                            destination_file = destination_dir / source_file.name
                            self.logger.warning(f"File not within base root, using flat copy:")
                            self.logger.warning(f"  Source: {source_file}")
                            self.logger.warning(f"  Base root: {base_root}")
                            self.logger.warning(f"  Error: {e}")
                            self.logger.warning(f"  Destination: {destination_file}")
                    else:
                        destination_file = destination_dir / source_file.name
                        self.logger.info(f"Flat copy: {source_file} -> {destination_file}")
                    
                    # Create destination directory if it doesn't exist
                    destination_file.parent.mkdir(parents=True, exist_ok=True)
                    self.logger.debug(f"Created directory: {destination_file.parent}")
                    
                    # Check if destination already exists
                    if destination_file.exists():
                        self.logger.debug(f"Destination file already exists, will overwrite: {destination_file}")
                    
                    # Copy file
                    shutil.copy2(source_file, destination_file)
                    
                    # Verify the copy was successful
                    if not destination_file.exists():
                        raise Exception(f"File was not copied successfully (destination does not exist)")
                    
                    operation = CopyOperation(
                        source_path=source_file,
                        destination_path=destination_file,
                        success=True,
                        file_size=source_file.stat().st_size
                    )
                    
                    self.logger.info(f"Successfully copied: {source_file.name} -> {destination_file}")
                    
                except Exception as e:
                    operation = CopyOperation(
                        source_path=source_file,
                        destination_path=destination_file if 'destination_file' in locals() else Path("Unknown"),
                        success=False,
                        error_message=str(e)
                    )
                    
                    self.logger.error(f"Failed to copy {source_file}: {e}")
                
                operations.append(operation)
                self.copy_progress.emit(i + 1, total_files)
            
            self.copy_completed.emit(operations)
            
            successful_count = len([op for op in operations if op.success])
            failed_count = len(operations) - successful_count
            self.logger.info(f"Copy operation completed. {successful_count} files copied successfully, {failed_count} failed")
            
        except Exception as e:
            self.logger.error(f"Error during copy operation: {e}")
            self.copy_error.emit(str(e))
        
        return operations
    
    def _get_session_files(self, sandbox_path: Path) -> List[Path]:
        """Get all files in a session sandbox"""
        files = []
        try:
            for root, dirs, file_names in os.walk(sandbox_path):
                for file_name in file_names:
                    files.append(Path(root) / file_name)
        except Exception as e:
            self.logger.error(f"Error getting session files: {e}")
        return files
    
    def _find_common_root(self, file_paths: List[Path]) -> Optional[Path]:
        """Find common root path for a list of files"""
        if not file_paths:
            return None
        
        try:
            # Convert all paths to absolute paths for consistent comparison
            abs_paths = [file_path.resolve() for file_path in file_paths]
            
            if len(abs_paths) == 1:
                # If only one file, return its parent directory
                return abs_paths[0].parent
            
            # Find the longest common prefix of all file paths
            first_path_parts = abs_paths[0].parts
            common_parts = []
            
            for i, part in enumerate(first_path_parts):
                # Check if all other paths have the same part at position i
                if all(len(path.parts) > i and path.parts[i] == part for path in abs_paths):
                    common_parts.append(part)
                else:
                    break
            
            if common_parts:
                common_root = Path(*common_parts)
                self.logger.debug(f"Found common root: {common_root} for {len(file_paths)} files")
                return common_root
            else:
                self.logger.debug("No common root found, files will be copied to destination root")
                return None
            
        except Exception as e:
            self.logger.error(f"Error finding common root: {e}")
            return None
    
    def get_file_types(self, file_paths: List[Path]) -> Dict[str, List[Path]]:
        """Group files by type/extension"""
        file_types = {}
        
        for file_path in file_paths:
            extension = file_path.suffix.lower()
            if not extension:
                extension = "No Extension"
            
            if extension not in file_types:
                file_types[extension] = []
            
            file_types[extension].append(file_path)
        
        return file_types
    
    def calculate_total_size(self, file_paths: List[Path]) -> int:
        """Calculate total size of files"""
        total_size = 0
        for file_path in file_paths:
            try:
                total_size += file_path.stat().st_size
            except (OSError, FileNotFoundError):
                continue
        return total_size
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def is_ue_asset_file(self, file_path: Path) -> bool:
        """Check if file is a UE asset file"""
        ue_extensions = {'.uasset', '.umap', '.uexp', '.ubulk', '.uptnl'}
        return file_path.suffix.lower() in ue_extensions
    
    def is_config_file(self, file_path: Path) -> bool:
        """Check if file is a configuration file"""
        config_extensions = {'.ini', '.json', '.cfg', '.config'}
        return file_path.suffix.lower() in config_extensions
    
    def is_source_file(self, file_path: Path) -> bool:
        """Check if file is a source code file"""
        source_extensions = {'.cpp', '.h', '.cs', '.py', '.js', '.html', '.css'}
        return file_path.suffix.lower() in source_extensions 