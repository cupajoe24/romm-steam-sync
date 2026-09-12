"""Unit tests for centralized logging setup."""

import logging
from pathlib import Path
import tempfile

from romm_steam_sync.logging_config import setup_logging


def test_setupLogging_configuresFileAndStreamHandlers(tmp_path):
    # Arrange
    log_file = tmp_path / "test_app.log"

    try:
        # Act
        setup_logging(log_level=logging.DEBUG, log_file=log_file)
        logger = logging.getLogger("test_module")
        logger.info("Test log message for unit testing")

        # Assert
        assert log_file.exists()
        log_content = log_file.read_text(encoding="utf-8")
        assert "Test log message for unit testing" in log_content
    finally:
        # Cleanup file handlers to release Windows file lock
        root_logger = logging.getLogger()
        for h in list(root_logger.handlers):
            h.close()
            root_logger.removeHandler(h)
        logging.shutdown()
