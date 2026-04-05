"""
Agentic - Application configuration.
Reads/writes a JSON config file in the user's data directory.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

from utils.logger import build_logger

log = build_logger("agentic.config")

_DEFAULT: dict[str, Any] = {
    "model_id": "google/gemma-3-1b-it",
    "hf_token": "",
    "device": "auto",
    "quantize_4bit": False,
    "theme": "dark",
    "font_size": 13,
    "max_parallel_tasks": 4,
    "working_memory_limit": 20,
    "streaming_enabled": True,
    "skill_timeout_s": 30,
    "log_level": "INFO",
}


class Config:
    """Thread-safe application configuration backed by a JSON file."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._path = self._locate()
        self._data: dict[str, Any] = dict(_DEFAULT)
        self._load()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _locate() -> Path:
        base = Path(os.environ.get("AGENTIC_DATA_DIR", Path.home() / ".agentic"))
        base.mkdir(parents=True, exist_ok=True)
        return base / "config.json"

    def _load(self) -> None:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                for key, default in _DEFAULT.items():
                    self._data[key] = raw.get(key, default)
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Config read error (%s) – using defaults", exc)

    def _save(self) -> None:
        try:
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            log.warning("Config write error: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, fallback: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, fallback)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._save()

    def update(self, mapping: dict[str, Any]) -> None:
        with self._lock:
            self._data.update(mapping)
            self._save()

    def all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)

    @property
    def data_dir(self) -> Path:
        return self._path.parent


# Singleton instance
cfg = Config()
