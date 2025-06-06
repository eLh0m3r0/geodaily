"""
Logging configuration for the Geopolitical Daily newsletter.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

try:
    from .config import Config
except ImportError:
    from config import Config

def setup_logger(
    name: str = "geodaily",
    log_file: Optional[str] = None,
    level: str = None
) -> logging.Logger:
    """
    Set up a logger with both console and file handlers.
    
    Args:
        name: Logger name
        log_file: Optional log file path. If None, uses default naming
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    
    # Set level
    log_level = getattr(logging, (level or Config.LOG_LEVEL).upper())
    logger.setLevel(log_level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Create formatter
    formatter = logging.Formatter(Config.LOG_FORMAT)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = Config.LOGS_DIR / f"geodaily_{timestamp}.log"
    
    # Ensure logs directory exists
    Config.create_directories()
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

def get_logger(name: str = "geodaily") -> logging.Logger:
    """Get or create a logger instance."""
    return logging.getLogger(name) or setup_logger(name)
