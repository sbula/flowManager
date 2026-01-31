import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

def setup_logger(
    name: str = "flow_manager", 
    log_file: Optional[Path] = None, 
    level: int = logging.INFO
) -> logging.Logger:
    """
    Configures and returns a centralized logger.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler (if path provided)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        # 5MB limit, 3 backups (Standard V7 Spec)
        file_handler = RotatingFileHandler(
            str(log_file), 
            maxBytes=5*1024*1024, 
            backupCount=3, 
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

def get_logger(name: str = "flow_manager") -> logging.Logger:
    return logging.getLogger(name)
