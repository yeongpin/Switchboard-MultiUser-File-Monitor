# -*- coding: utf-8 -*-
"""
Core modules for Switchboard MultiUser File Monitor
"""

# Always import config detector (no PySide6 dependency)
from .config_detector import ConfigDetector, SwitchboardConfig

# Initialize available modules list
__all__ = ['ConfigDetector', 'SwitchboardConfig']

# Try to import PySide6-dependent modules
try:
    from .file_monitor import FileMonitor, MultiUserSession
    __all__.extend(['FileMonitor', 'MultiUserSession'])
except ImportError:
    pass

try:
    from .file_manager import FileManager, CopyOperation
    __all__.extend(['FileManager', 'CopyOperation'])
except ImportError:
    pass 