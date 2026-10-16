import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.security import sanitize_sensitive_data
from app.core.config import get_settings


class SensitiveDataFilter(logging.Filter):
    """Logging filter that scrubs sensitive keys, tokens, and credentials from all log records."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_sensitive_data(record.msg, self.api_key)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: sanitize_sensitive_data(str(v), self.api_key)
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    sanitize_sensitive_data(str(arg), self.api_key)
                    for arg in record.args
                )
        return True


def setup_logger(
    name: str = "smartlead_analytics",
    log_level: Optional[str] = None,
    log_dir: str = "logs"
) -> logging.Logger:
    """Sets up a logger with sanitization filter, console output, and daily timestamped file output."""
    settings = get_settings()
    level_str = log_level or settings.log_level
    level = getattr(logging, level_str.upper(), logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    # Ensure logs directory exists
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    log_file_path = os.path.join(log_dir, f"app_{today_str}.log")

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    filter_instance = SensitiveDataFilter(api_key=settings.smartlead_api_key)

    # File Handler
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(filter_instance)
    logger.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(filter_instance)
    logger.addHandler(console_handler)

    return logger


logger = setup_logger()
