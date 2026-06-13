"""Logging configuration shared across the framework.

Provides a single configured logger factory. Logs are written both to the
console (for live CI output) and to a timestamped file under /logs, so every
major step is traceable after the run.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from config.config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Console (PowerShell) shows only critical lines; full DEBUG trace stays in the log file.
# Override with TESTRAIL_CONSOLE_LOG_LEVEL=INFO if verbose console output is needed.
_CONSOLE_LEVEL_NAME = (settings.console_log_level or "WARNING").upper()
_CONSOLE_LEVEL = getattr(logging, _CONSOLE_LEVEL_NAME, logging.WARNING)

# One log file per process invocation.
_LOG_FILE: Path = settings.logs_dir / f"run_{datetime.now():%Y%m%d_%H%M%S}.log"

_configured = False


def _configure_root() -> None:
    global _configured
    if _configured:
        return

    settings.logs_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("testrail")
    root.setLevel(logging.DEBUG)
    root.propagate = False

    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console = logging.StreamHandler(stream=sys.stdout)
    console.setLevel(_CONSOLE_LEVEL)
    console.setFormatter(formatter)

    file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root.addHandler(console)
    root.addHandler(file_handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced child logger of the configured `testrail` root."""
    _configure_root()
    return logging.getLogger(f"testrail.{name}")


def log_file_path() -> Path:
    """Absolute path of the current run log file (for Allure attachment)."""
    return _LOG_FILE
