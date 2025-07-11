# -*- coding: utf-8 -*-
"""
File Monitor Module
Monitors MultiUser intermediate directories for file changes
"""

import os
import time
from pathlib import Path
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from PySide6.QtCore import QThread, QTimer, Signal
from utils.logger import get_logger


@dataclass
class MultiUserSession:
    """MultiUser session information"""
    session_id: str
    user_id: str
    sandbox_path: Path
    last_modified: datetime
    file_count: int
    total_size: int
    
    def __str__(self):
        return f"{self.session_id} ({self.last_modified.strftime('%Y-%m-%d %H:%M:%S')})"


class FileMonitor(QThread):
    """Monitor MultiUser intermediate directories for changes"""
    
    # Signals
    session_found = Signal(MultiUserSession)
    session_updated = Signal(MultiUserSession)
    session_removed = Signal(str)  # session_id
    
    def __init__(self, multiuser_path: Path, poll_interval: int = 2):
        super().__init__()
        self.logger = get_logger(__name__)
        self.multiuser_path = multiuser_path
        self.poll_interval = poll_interval
        self.running = False
        self.sessions: Dict[str, MultiUserSession] = {}
        
    def run(self):
        """Main monitoring loop"""
        self.running = True
        self.logger.info(f"Starting file monitor for: {self.multiuser_path}")
        
        while self.running:
            try:
                self.scan_sessions()
                time.sleep(self.poll_interval)
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                time.sleep(self.poll_interval)
    
    def stop(self):
        """Stop the monitoring thread"""
        self.running = False
        self.logger.info("Stopping file monitor")
    
    def scan_sessions(self):
        """Scan for MultiUser sessions"""
        if not self.multiuser_path.exists():
            return
        
        current_sessions = set()
        
        try:
            # Scan session directories (UUID format)
            for session_dir in self.multiuser_path.iterdir():
                if not session_dir.is_dir():
                    continue
                
                session_id = session_dir.name
                if not self._is_valid_session_id(session_id):
                    continue
                
                # Scan user directories within session
                for user_dir in session_dir.iterdir():
                    if not user_dir.is_dir():
                        continue
                    
                    user_id = user_dir.name
                    if not self._is_valid_user_id(user_id):
                        continue
                    
                    # Check for Sandbox/Game directory
                    sandbox_path = user_dir / "Sandbox" / "Game"
                    if not sandbox_path.exists():
                        continue
                    
                    # Create session key
                    session_key = f"{session_id}_{user_id}"
                    current_sessions.add(session_key)
                    
                    # Get session info
                    self.logger.debug(f"Getting session info for: {session_key}")
                    session_info = self._get_session_info(session_key, session_id, user_id, sandbox_path)
                    self.logger.debug(f"Session info complete: {session_info.file_count} files, {session_info.total_size} bytes")
                    
                    if session_key in self.sessions:
                        # Check if session was updated (more sensitive detection)
                        old_session = self.sessions[session_key]
                        if (session_info.last_modified != old_session.last_modified or 
                            session_info.file_count != old_session.file_count or
                            session_info.total_size != old_session.total_size):
                            self.sessions[session_key] = session_info
                            self.session_updated.emit(session_info)
                            self.logger.debug(f"Session updated: {session_key} (files: {old_session.file_count}->{session_info.file_count}, size: {old_session.total_size}->{session_info.total_size})")
                        # If no changes, don't log anything to reduce spam
                    else:
                        # New session found
                        self.sessions[session_key] = session_info
                        self.session_found.emit(session_info)
                        self.logger.debug(f"New session found: {session_key}")
        
        except Exception as e:
            self.logger.error(f"Error scanning sessions: {e}")
        
        # Check for removed sessions
        removed_sessions = set(self.sessions.keys()) - current_sessions
        for session_key in removed_sessions:
            self.session_removed.emit(session_key)
            del self.sessions[session_key]
            self.logger.debug(f"Session removed: {session_key}")
    
    def _is_valid_session_id(self, session_id: str) -> bool:
        """Check if session ID looks like a valid UUID"""
        # More lenient check - allow any hex-like string with reasonable length
        return len(session_id) >= 8 and all(c in '0123456789ABCDEFabcdef_' for c in session_id)
    
    def _is_valid_user_id(self, user_id: str) -> bool:
        """Check if user ID looks like a valid UUID"""
        # More lenient check - allow any hex-like string with reasonable length
        return len(user_id) >= 8 and all(c in '0123456789ABCDEFabcdef_' for c in user_id)
    
    def _get_session_info(self, session_key: str, session_id: str, user_id: str, sandbox_path: Path) -> MultiUserSession:
        """Get detailed session information"""
        import time
        start_time = time.time()
        
        try:
            # Get last modified time and file count
            # Initialize with directory's own modification time as baseline
            try:
                dir_stat = sandbox_path.stat()
                last_modified = datetime.fromtimestamp(dir_stat.st_mtime)
            except (OSError, FileNotFoundError):
                # Fallback to current time if directory stat fails
                last_modified = datetime.now()
            
            file_count = 0
            total_size = 0
            
            # Use fast directory scanning with depth limit
            last_modified, file_count, total_size = self._scan_directory_fast(sandbox_path, last_modified, file_count, total_size, max_depth=5)
            
            # Log performance
            elapsed = time.time() - start_time
            self.logger.debug(f"Session scan completed in {elapsed:.2f}s: {file_count} files, {total_size} bytes")
            self.logger.debug(f"Session {session_key} last_modified: {last_modified.strftime('%Y-%m-%d %H:%M:%S')}")
            
            return MultiUserSession(
                session_id=session_id,
                user_id=user_id,
                sandbox_path=sandbox_path,
                last_modified=last_modified,
                file_count=file_count,
                total_size=total_size
            )
        
        except Exception as e:
            elapsed = time.time() - start_time
            self.logger.error(f"Error getting session info for {session_key} after {elapsed:.2f}s: {e}")
            return MultiUserSession(
                session_id=session_id,
                user_id=user_id,
                sandbox_path=sandbox_path,
                last_modified=datetime.now(),
                file_count=0,
                total_size=0
            )
    
    def _scan_directory_fast(self, path: Path, last_modified: datetime, file_count: int, total_size: int, max_depth: int = 5, current_depth: int = 0):
        """Fast directory scanning with depth limit"""
        if current_depth >= max_depth:
            return last_modified, file_count, total_size
        
        try:
            # Use iterdir instead of listdir for better performance
            items = []
            count = 0
            for item in path.iterdir():
                items.append(item)
                count += 1
                # Limit the number of items processed to avoid hanging
                if count > 1000:  # Safety limit
                    self.logger.warning(f"Too many items in {path}, limiting scan")
                    break
            
            # Process files first (faster)
            for item in items:
                if item.is_file():
                    try:
                        stat = item.stat()
                        file_modified = datetime.fromtimestamp(stat.st_mtime)
                        if file_modified > last_modified:
                            last_modified = file_modified
                        file_count += 1
                        total_size += stat.st_size
                    except (OSError, FileNotFoundError):
                        continue
            
            # Then process directories (with depth limit)
            for item in items:
                if item.is_dir():
                    last_modified, file_count, total_size = self._scan_directory_fast(
                        item, last_modified, file_count, total_size, max_depth, current_depth + 1
                    )
                    
        except (OSError, PermissionError) as e:
            self.logger.debug(f"Cannot access directory {path}: {e}")
        except Exception as e:
            self.logger.warning(f"Unexpected error scanning {path}: {e}")
        
        return last_modified, file_count, total_size
    
    def get_session_files(self, session: MultiUserSession) -> List[Path]:
        """Get list of files in a session"""
        files = []
        try:
            for root, dirs, file_names in os.walk(session.sandbox_path):
                for file_name in file_names:
                    files.append(Path(root) / file_name)
        except Exception as e:
            self.logger.error(f"Error getting session files: {e}")
        return files
    
    def get_modified_files(self, session: MultiUserSession, since: datetime) -> List[Path]:
        """Get files modified since a specific time"""
        modified_files = []
        try:
            for root, dirs, file_names in os.walk(session.sandbox_path):
                for file_name in file_names:
                    file_path = Path(root) / file_name
                    try:
                        stat = file_path.stat()
                        file_modified = datetime.fromtimestamp(stat.st_mtime)
                        if file_modified > since:
                            modified_files.append(file_path)
                    except (OSError, FileNotFoundError):
                        continue
        except Exception as e:
            self.logger.error(f"Error getting modified files: {e}")
        return modified_files 