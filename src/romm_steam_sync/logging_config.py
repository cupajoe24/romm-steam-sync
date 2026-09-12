"""Centralized logging configuration for romm-steam-sync."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from romm_steam_sync.config import get_default_config_dir


def setup_logging(
    log_level: int = logging.INFO, log_file: Optional[Path] = None
) -> None:
    """Configure the root logger with console and rotating file handlers.

    Args:
        log_level: Logging verbosity level (defaults to logging.INFO).
        log_file: Optional path to the log file. Defaults to
            '%APPDATA%/romm-steam-sync/romm-steam-sync.log'.
    """
    if log_file is None:
        log_file = get_default_config_dir() / "romm-steam-sync.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Prevent duplicate handlers
    has_stream_handler = any(
        isinstance(h, logging.StreamHandler)
        and not isinstance(h, RotatingFileHandler)
        for h in root_logger.handlers
    )
    has_file_handler = any(
        isinstance(h, RotatingFileHandler) for h in root_logger.handlers
    )

    if not has_stream_handler:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(log_level)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    if not has_file_handler:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=5 * 1024 * 1024,  # 5 MB
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            root_logger.warning(
                "Failed to initialize file logger at %s: %s", log_file, e
            )


def close_logging_file_handlers() -> None:
    """Close and remove all RotatingFileHandler instances from root logger.

    Releases file locks on the log file so it can be moved, backed up, or deleted.
    """
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        if isinstance(handler, RotatingFileHandler):
            try:
                handler.close()
            except Exception as e:
                root_logger.debug("Error while closing RotatingFileHandler: %s", e)
            root_logger.removeHandler(handler)
