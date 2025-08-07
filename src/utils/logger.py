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
    """Setup main application logger"""
    
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
    
    # Remove existing handlers
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
    
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """Get logger instance"""
    if name:
        logger_name = f"SwitchboardMonitor.{name}"
    else:
        logger_name = "SwitchboardMonitor"
    
    logger = logging.getLogger(logger_name)
    
    # Only setup if not already configured
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Prevent propagation to avoid duplicate messages
        logger.propagate = False
    
    return logger 