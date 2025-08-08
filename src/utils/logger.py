# -*- coding: utf-8 -*-
"""
Logger Utility Module
Provides logging functionality for the application
"""

import logging
import os
from pathlib import Path
from datetime import datetime


def setup_logger(name: str = "SwitchboardMonitor", level: int = logging.INFO) -> logging.Logger:
    """Setup the root application logger once and return it.

    This logger owns all handlers (console + file). Child loggers should NOT
    add their own handlers; they should propagate to this root so that all
    messages are captured to the same file.
    """
    
    # Create logs directory in user's Documents
    documents_path = Path.home() / "Documents"
    logs_base_dir = documents_path / "SwitchboardSync" / "logs"
    logs_base_dir.mkdir(parents=True, exist_ok=True)
    
    # Create date-specific subdirectory
    date_str = datetime.now().strftime('%Y%m%d')
    logs_dir = logs_base_dir / date_str
    logs_dir.mkdir(exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers (reconfigure idempotently)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    log_file = logs_dir / f"{name}_{datetime.now().strftime('%H%M%S')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Do not propagate to the root logger to avoid duplicate prints
    logger.propagate = False

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger that writes to the main "SwitchboardMonitor" logger.

    - Ensures the root logger is configured (calls setup_logger() on-demand)
    - Child loggers do NOT create handlers; they propagate to the root
    - All module logs end up in the same file and console stream
    """
    root_name = "SwitchboardMonitor"
    root_logger = logging.getLogger(root_name)

    # Ensure the root logger is configured with handlers
    if not root_logger.handlers:
        root_logger = setup_logger(root_name)

    if name and name != root_name:
        # Use proper hierarchical child to guarantee propagation
        child_logger = root_logger.getChild(name)
    else:
        child_logger = root_logger

    # Child should not own handlers; route to root
    for handler in child_logger.handlers[:]:
        child_logger.removeHandler(handler)
    child_logger.setLevel(root_logger.level)
    child_logger.propagate = True

    return child_logger