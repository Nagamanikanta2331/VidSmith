"""Logging configuration for MediaForge."""

import logging
import logging.handlers
import os
from pathlib import Path


def configure_logging(debug: bool) -> None:
    """Configure the root logger for MediaForge.

    If debug is True, a RotatingFileHandler is attached writing to
    %APPDATA%/MediaForge/mediaforge.log.
    If debug is False, a NullHandler is attached.
    """
    root_logger = logging.getLogger("mediaforge")
    root_logger.setLevel(logging.DEBUG if debug else logging.CRITICAL)

    # Remove existing handlers to avoid duplicates if called multiple times
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    if debug:
        # Determine log directory
        appdata = os.environ.get("APPDATA")
        if appdata:
            log_dir = Path(appdata) / "MediaForge"
        else:
            xdg = os.environ.get("XDG_CONFIG_HOME")
            base = Path(xdg) if xdg else Path.home() / ".config"
            log_dir = base / "mediaforge"

        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "mediaforge.log"

        # 5 MB max per file, keeping 3 backups
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
        root_logger.debug("Debug logging initialized.")
    else:
        root_logger.addHandler(logging.NullHandler())
