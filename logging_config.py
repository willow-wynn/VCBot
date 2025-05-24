"""Logging configuration for VCBot"""

import logging
import sys
from pathlib import Path
from datetime import datetime


class DebugFileFilter(logging.Filter):
    """Filter that only allows DEBUG level messages"""
    def filter(self, record):
        return record.levelno == logging.DEBUG


class NonDebugFilter(logging.Filter):
    """Filter that excludes DEBUG level messages"""
    def filter(self, record):
        return record.levelno > logging.DEBUG


def setup_logging(console_level: str = "INFO", logs_dir: Path = None):
    """Configure logging with debug to timestamped files, info/error to terminal"""
    
    # Create timestamped debug log file
    if logs_dir is None:
        logs_dir = Path.cwd() / "logs"
    
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    start_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    debug_log_file = logs_dir / f"vcbot_{start_time}.log"
    
    # Custom formatters
    console_formatter = logging.Formatter(
        '[%(levelname)s] %(name)s: %(message)s'
    )
    
    file_formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler - INFO and above only (no DEBUG)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(getattr(logging, console_level.upper()))
    console_handler.addFilter(NonDebugFilter())
    
    # Debug file handler - DEBUG messages only
    debug_handler = logging.FileHandler(debug_log_file)
    debug_handler.setFormatter(file_formatter)
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.addFilter(DebugFileFilter())
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,  # Root logger gets all, handlers filter
        handlers=[console_handler, debug_handler],
        force=True  # Override any existing config
    )
    
    # Set specific log levels for noisy libraries
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.http').setLevel(logging.WARNING)
    logging.getLogger('discord.gateway').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Create logger for our bot
    logger = logging.getLogger('vcbot')
    logger.setLevel(logging.DEBUG)  # Allow all levels, handlers will filter
    
    # Log the setup completion
    logger.info(f"Logging initialized - Debug: {debug_log_file}")
    logger.debug("Debug logging active - this message goes to file only")
    
    return logger


# Global logger instance
logger = logging.getLogger('vcbot')