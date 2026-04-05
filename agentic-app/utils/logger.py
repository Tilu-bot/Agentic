"""
Agentic - Structured logging system.
Uses rotating file handler and a rich console formatter.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path


def _log_dir() -> Path:
    base = Path(os.environ.get("AGENTIC_DATA_DIR", Path.home() / ".agentic"))
    log_path = base / "logs"
    log_path.mkdir(parents=True, exist_ok=True)
    return log_path


def build_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)-24s %(message)s",
        datefmt="%H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)

    try:
        fh = logging.handlers.RotatingFileHandler(
            _log_dir() / "agentic.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        pass

    logger.addHandler(console)
    logger.propagate = False
    return logger


root_log = build_logger("agentic")
