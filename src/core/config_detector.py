# -*- coding: utf-8 -*-
"""
Config Detector Module
Detects and parses Switchboard configuration files
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from utils.logger import get_logger


@dataclass
class SwitchboardConfig:
    """Switchboard configuration data"""
    project_name: str
    uproject_path: str
    engine_dir: str
    multiuser_server_name: str
    multiuser_working_dir: str
    config_file_path: str
    
    def get_multiuser_path(self) -> Optional[Path]:
        """Get the MultiUser intermediate directory path"""
        if self.multiuser_working_dir:
            return Path(self.multiuser_working_dir)
        
        candidate_paths = []
        
        # Try project-based MultiUser path first
        if self.uproject_path:
            project_dir = Path(self.uproject_path).parent
            project_multiuser = project_dir / "Intermediate" / "Concert" / "MultiUser"
            if project_multiuser.exists():
                candidate_paths.append(project_multiuser)
        
        # Try engine-based MultiUser path
        if self.engine_dir:
            engine_multiuser = Path(self.engine_dir) / "Programs" / "UnrealMultiUserSlateServer" / "Intermediate" / "MultiUser"
            if engine_multiuser.exists():
                candidate_paths.append(engine_multiuser)
        
        # Choose the path with actual session data
        for path in candidate_paths:
            if self._has_active_sessions(path):
                return path
        
        # If no path has sessions, return the first available one
        return candidate_paths[0] if candidate_paths else None
    
    def _has_active_sessions(self, multiuser_path: Path) -> bool:
        """Check if a MultiUser path has active sessions"""
        if not multiuser_path.exists():
            return False
        
        try:
            for session_dir in multiuser_path.iterdir():
                if not session_dir.is_dir():
                    continue
                
                # Check if it looks like a session ID
                session_id = session_dir.name
                if len(session_id) >= 8 and all(c in '0123456789ABCDEFabcdef_' for c in session_id):
                    # Check for user directories within session
                    for user_dir in session_dir.iterdir():
                        if not user_dir.is_dir():
                            continue
                        
                        user_id = user_dir.name
                        if len(user_id) >= 8 and all(c in '0123456789ABCDEFabcdef_' for c in user_id):
                            # Check for Sandbox/Game directory
                            sandbox_game_path = user_dir / "Sandbox" / "Game"
                            if sandbox_game_path.exists():
                                return True
        except Exception:
            pass
        
        return False
    
    def get_project_content_dir(self) -> Optional[Path]:
        """Get the project Content directory"""
        if self.uproject_path:
            project_dir = Path(self.uproject_path).parent
            return project_dir / "Content"
        return None


class ConfigDetector:
    """Detects and manages Switchboard configuration"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.switchboard_path = self._find_switchboard_path()
        self.config = None
        
    def _find_switchboard_path(self) -> Optional[Path]:
        """Find Switchboard installation path"""
        # Check common Switchboard locations
        common_paths = [
            Path("D:/UE_5.6/Engine/Plugins/VirtualProduction/Switchboard/Source/Switchboard"),
            Path("C:/Program Files/Epic Games/UE_5.6/Engine/Plugins/VirtualProduction/Switchboard/Source/Switchboard"),
            # Add more common paths as needed
        ]
        
        for path in common_paths:
            if path.exists() and (path / "switchboard").exists():
                self.logger.info(f"Found Switchboard at: {path}")
                return path
        
        # Try to find from environment or current directory
        current_dir = Path.cwd()
        while current_dir != current_dir.parent:
            switchboard_dir = current_dir / "switchboard"
            if switchboard_dir.exists():
                self.logger.info(f"Found Switchboard at: {current_dir}")
                return current_dir
            current_dir = current_dir.parent
        
        self.logger.warning("Could not find Switchboard installation")
        return None
    
    def _get_config_manager(self):
        """Import and get ConfigManager from Switchboard"""
        if not self.switchboard_path:
            return None
            
        try:
            # Add multiple possible paths to sys.path
            possible_paths = [
                str(self.switchboard_path),
                str(self.switchboard_path / "switchboard"),
                str(self.switchboard_path / "Source" / "Switchboard"),
                str(self.switchboard_path.parent),  # Parent directory
            ]
            
            # Add all possible paths
            for path in possible_paths:
                if path not in sys.path and Path(path).exists():
                    sys.path.insert(0, path)
                    self.logger.debug(f"Added to Python path: {path}")
            
            # Try to import config module
            try:
                from config import CONFIG_MGR, SETTINGS
                self.logger.info("Successfully imported Switchboard config")
                return CONFIG_MGR, SETTINGS
            except ImportError:
                # Try alternative import path
                import importlib.util
                config_file = self.switchboard_path / "switchboard" / "config.py"
                if config_file.exists():
                    spec = importlib.util.spec_from_file_location("switchboard_config", config_file)
                    config_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(config_module)
                    
                    if hasattr(config_module, 'CONFIG_MGR') and hasattr(config_module, 'SETTINGS'):
                        self.logger.info("Successfully imported Switchboard config via file path")
                        return config_module.CONFIG_MGR, config_module.SETTINGS
                
                raise ImportError("Could not import config module")
                
        except ImportError as e:
            self.logger.error(f"Failed to import Switchboard config: {e}")
            self.logger.error("This might be because:")
            self.logger.error("1. Switchboard is not properly installed")
            self.logger.error("2. Python dependencies are missing")
            self.logger.error("3. The Switchboard version is incompatible")
            return None, None
        except Exception as e:
            self.logger.error(f"Unexpected error importing Switchboard config: {e}")
            return None, None
    
    def detect_current_config(self) -> Optional[SwitchboardConfig]:
        """Detect currently loaded Switchboard configuration"""
        config_mgr, settings = self._get_config_manager()
        if not config_mgr or not settings:
            return None
            
        try:
            # Get current config path from settings
            # Try different possible attribute names for the config
            current_config_path = None
            
            # Try various possible attribute names
            for attr_name in ['CONFIG', 'config', 'current_config', 'config_path']:
                if hasattr(settings, attr_name):
                    current_config_path = getattr(settings, attr_name)
                    self.logger.debug(f"Found config path via {attr_name}: {current_config_path}")
                    break
            
            if not current_config_path:
                self.logger.warning("No current config found in settings")
                # Try to get config from CONFIG_MGR instead
                if hasattr(config_mgr, 'get_current_config'):
                    current_config_path = config_mgr.get_current_config()
                elif hasattr(config_mgr, 'current_config'):
                    current_config_path = config_mgr.current_config
                else:
                    return None
            
            # Load config file
            config_data = self._load_config_file(current_config_path)
            if not config_data:
                return None
            
            # Create SwitchboardConfig object
            self.config = SwitchboardConfig(
                project_name=config_data.get('project_name', 'Unknown'),
                uproject_path=config_data.get('uproject', ''),
                engine_dir=config_data.get('engine_dir', ''),
                multiuser_server_name=config_data.get('muserver_server_name', ''),
                multiuser_working_dir=config_data.get('muserver_working_dir', ''),
                config_file_path=str(current_config_path)
            )
            
            self.logger.info(f"Loaded config: {self.config.project_name}")
            return self.config
            
        except Exception as e:
            self.logger.error(f"Error detecting config: {e}")
            return None
    
    def _load_config_file(self, config_path: Path) -> Optional[Dict[str, Any]]:
        """Load configuration file"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading config file {config_path}: {e}")
            return None
    
    def get_available_configs(self) -> list[Path]:
        """Get list of available configuration files"""
        config_mgr, _ = self._get_config_manager()
        if not config_mgr:
            return []
        
        try:
            return config_mgr.list_config_paths()
        except Exception as e:
            self.logger.error(f"Error listing config paths: {e}")
            return []
    
    def load_config_by_path(self, config_path: Path) -> Optional[SwitchboardConfig]:
        """Load specific configuration by path"""
        config_data = self._load_config_file(config_path)
        if not config_data:
            return None
        
        return SwitchboardConfig(
            project_name=config_data.get('project_name', 'Unknown'),
            uproject_path=config_data.get('uproject', ''),
            engine_dir=config_data.get('engine_dir', ''),
            multiuser_server_name=config_data.get('muserver_server_name', ''),
            multiuser_working_dir=config_data.get('muserver_working_dir', ''),
            config_file_path=str(config_path)
        )
    
    def _scan_multiuser_directories(self) -> list[Path]:
        """Scan for MultiUser directories when Switchboard is not available"""
        multiuser_paths = []
        
        # Common MultiUser locations
        common_locations = [
            Path("D:/UE_5.6/Engine/Programs/UnrealMultiUserSlateServer/Intermediate/MultiUser"),
            Path("C:/Program Files/Epic Games/UE_5.6/Engine/Programs/UnrealMultiUserSlateServer/Intermediate/MultiUser"),
        ]
        
        # Add project-based paths - check common project locations
        project_locations = [
            Path("C:/Users").expanduser(),
            Path("D:/"),
            Path("E:/"),
            Path.cwd(),
        ]
        
        for base_path in project_locations:
            if not base_path.exists():
                continue
                
            # Look for Unreal Projects directories
            for projects_dir in ["Documents/Unreal Projects", "UnrealProjects", "Projects"]:
                projects_path = base_path / projects_dir
                if projects_path.exists():
                    # Scan for project directories
                    try:
                        for project_dir in projects_path.iterdir():
                            if project_dir.is_dir():
                                multiuser_dir = project_dir / "Intermediate" / "Concert" / "MultiUser"
                                if multiuser_dir.exists():
                                    common_locations.append(multiuser_dir)
                    except PermissionError:
                        continue
        
        # Check current directory and parent directories for project-based paths
        current_dir = Path.cwd()
        while current_dir != current_dir.parent:
            project_multiuser = current_dir / "Intermediate" / "Concert" / "MultiUser"
            if project_multiuser.exists():
                common_locations.append(project_multiuser)
            current_dir = current_dir.parent
        
        # Remove duplicates and check existence
        for location in set(common_locations):
            if location.exists():
                multiuser_paths.append(location)
                self.logger.info(f"Found MultiUser directory: {location}")
        
        if not multiuser_paths:
            self.logger.warning("No MultiUser directories found")
            
        return multiuser_paths
    
    def get_active_sessions(self) -> list[Path]:
        """Get active MultiUser sessions"""
        config_mgr, settings = self._get_config_manager()
        if config_mgr:
            # This is a placeholder - actual implementation would depend on
            # Switchboard's internal structure
            try:
                # Try to get sessions from Switchboard
                return []
            except Exception as e:
                self.logger.error(f"Error getting sessions from Switchboard: {e}")
        
        # Fallback: directly scan for MultiUser directories
        return self._scan_multiuser_directories()
    
    def get_fallback_config(self) -> Optional[SwitchboardConfig]:
        """Get a fallback configuration when Switchboard is not available"""
        multiuser_paths = self._scan_multiuser_directories()
        if not multiuser_paths:
            return None
        
        # Use the first available MultiUser directory
        multiuser_path = multiuser_paths[0]
        
        # Try to infer project information from the path
        project_dir = multiuser_path
        while project_dir.parent != project_dir:
            if (project_dir / "Content").exists():
                # Found project directory
                project_name = project_dir.name
                uproject_files = list(project_dir.glob("*.uproject"))
                uproject_path = str(uproject_files[0]) if uproject_files else ""
                
                return SwitchboardConfig(
                    project_name=project_name,
                    uproject_path=uproject_path,
                    engine_dir="",
                    multiuser_server_name="",
                    multiuser_working_dir=str(multiuser_path),
                    config_file_path=""
                )
            project_dir = project_dir.parent
        
        # If we can't find a project, create a basic config
        return SwitchboardConfig(
            project_name="Unknown Project",
            uproject_path="",
            engine_dir="",
            multiuser_server_name="",
            multiuser_working_dir=str(multiuser_path),
            config_file_path=""
        )
    
    def is_switchboard_available(self) -> bool:
        """Check if Switchboard is available"""
        config_mgr, settings = self._get_config_manager()
        return config_mgr is not None and settings is not None 