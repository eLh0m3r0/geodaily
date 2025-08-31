"""
Logging configuration for the Geopolitical Daily newsletter.
BACKWARD COMPATIBILITY MODULE - Use src.logging for new structured logging.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

from .config import Config
from .logging_system import StructuredLogger, setup_structured_logging

# Global reference to structured logger for backward compatibility
_structured_logger = None

def setup_logger(
    name: str = "geodaily",
    log_file: Optional[str] = None,
    level: str = None
) -> logging.Logger:
    """
    Set up a logger with both console and file handlers.
    BACKWARD COMPATIBILITY: This now uses structured logging internally.

    Args:
        name: Logger name
        log_file: Optional log file path. If None, uses default naming
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance (backward compatible)
    """
    global _structured_logger

    # Initialize structured logging if not already done
    if _structured_logger is None:
        _structured_logger = setup_structured_logging()

    # Create a wrapper logger that maintains backward compatibility
    class BackwardCompatibleLogger(logging.Logger):
        """Logger that wraps structured logging for backward compatibility."""

        def __init__(self, name: str, structured_logger: StructuredLogger):
            super().__init__(name)
            self.structured_logger = structured_logger
            self.setLevel(getattr(logging, (level or Config.LOG_LEVEL).upper()))

        def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False):
            """Override _log to use structured logging."""
            # Convert logging level to structured logger method
            if level >= logging.CRITICAL:
                self.structured_logger.critical(msg, structured_data=extra)
            elif level >= logging.ERROR:
                self.structured_logger.error(msg, structured_data=extra)
            elif level >= logging.WARNING:
                self.structured_logger.warning(msg, structured_data=extra)
            elif level >= logging.INFO:
                self.structured_logger.info(msg, structured_data=extra)
            elif level >= logging.DEBUG:
                self.structured_logger.debug(msg, structured_data=extra)

    # Return backward compatible logger
    return BackwardCompatibleLogger(name, _structured_logger)

def get_logger(name: str = "geodaily") -> logging.Logger:
    """Get or create a logger instance (backward compatible)."""
    return logging.getLogger(name) or setup_logger(name)

# For new code, use these imports instead:
# from .logging import StructuredLogger, get_structured_logger, setup_structured_logging
