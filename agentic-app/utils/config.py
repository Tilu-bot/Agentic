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

# Schema defining the expected type and optional constraints for each config key.
# "type"    → Python type the value must be coerced to.
# "choices" → set of allowed string values (strings only).
# "min"/"max" → inclusive integer range.
_CONFIG_SCHEMA: dict[str, dict] = {
    "model_id":             {"type": str},
    "hf_token":             {"type": str},
    "device":               {"type": str, "choices": {"auto", "cpu", "cuda", "mps"}},
    "quantize_4bit":        {"type": bool},
    "theme":                {"type": str, "choices": {"dark", "light"}},
    "font_size":            {"type": int, "min": 8,  "max": 32},
    "max_parallel_tasks":   {"type": int, "min": 1,  "max": 32},
    "working_memory_limit": {"type": int, "min": 5,  "max": 200},
    "streaming_enabled":    {"type": bool},
    "skill_timeout_s":      {"type": int, "min": 5,  "max": 300},
    "log_level":            {"type": str, "choices": {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}},
    "react_max_iterations": {"type": int, "min": 1,  "max": 20},
    "context_limit_tokens": {"type": int, "min": 512, "max": 131072},
    "skill_retry_budget":   {"type": int, "min": 0,  "max": 3},
}


def _validate_value(key: str, value: Any) -> tuple[Any, str | None]:
    """
    Coerce *value* to the declared type for *key* and check constraints.

    Returns ``(coerced_value, None)`` on success or
    ``(value, error_message)`` if the value cannot be coerced or violates
    a constraint.  Unknown keys pass through unchanged with no error.
    """
    schema = _CONFIG_SCHEMA.get(key)
    if schema is None:
        return value, None

    expected_type = schema["type"]

    # Coerce booleans before numeric check (bool is a subclass of int).
    if expected_type is bool:
        if isinstance(value, bool):
            coerced: Any = value
        elif isinstance(value, int):
            coerced = bool(value)
        elif isinstance(value, str):
            if value.lower() in ("true", "1", "yes"):
                coerced = True
            elif value.lower() in ("false", "0", "no"):
                coerced = False
            else:
                return value, f"Config '{key}': cannot coerce {value!r} to bool"
        else:
            return value, f"Config '{key}': expected bool, got {type(value).__name__}"
    elif expected_type is int:
        try:
            coerced = int(value)
        except (ValueError, TypeError):
            return value, f"Config '{key}': expected int, got {value!r}"
        if "min" in schema and coerced < schema["min"]:
            return value, f"Config '{key}': {coerced} < min {schema['min']}"
        if "max" in schema and coerced > schema["max"]:
            return value, f"Config '{key}': {coerced} > max {schema['max']}"
    elif expected_type is str:
        if not isinstance(value, str):
            return value, f"Config '{key}': expected str, got {type(value).__name__}"
        coerced = value
        if "choices" in schema and coerced not in schema["choices"]:
            return value, (
                f"Config '{key}': {coerced!r} not in {sorted(schema['choices'])}"
            )
    else:
        coerced = value

    return coerced, None


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
    # ReAct loop: maximum reasoning–action iterations per deliberation pulse.
    # Each iteration generates a response, runs any requested skills, and feeds
    # results back to the model before the next iteration.  6 covers most
    # multi-step tasks while preventing runaway loops.
    "react_max_iterations": 6,
    # Approximate token limit for the assembled prompt (system + messages).
    # When this limit is approached (85 % threshold) the oldest messages are
    # automatically trimmed from the conversation history to keep the prompt
    # within bounds.  Most small open-source models support 4096–8192 tokens.
    "context_limit_tokens": 4096,
    # Maximum number of retry attempts for a single skill invocation when it
    # returns an error.  0 means no retries (fail immediately).  Each retry
    # uses an exponential back-off delay (0.5 s × attempt).
    "skill_retry_budget": 1,
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
        coerced, err = _validate_value(key, value)
        if err:
            log.warning("Config validation rejected set(%s): %s", key, err)
            return
        with self._lock:
            self._data[key] = coerced
            self._save()

    def update(self, mapping: dict[str, Any]) -> None:
        validated: dict[str, Any] = {}
        for key, value in mapping.items():
            coerced, err = _validate_value(key, value)
            if err:
                log.warning("Config validation rejected update(%s): %s", key, err)
            else:
                validated[key] = coerced
        with self._lock:
            self._data.update(validated)
            self._save()

    def all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)

    @property
    def data_dir(self) -> Path:
        return self._path.parent


# Singleton instance
cfg = Config()
