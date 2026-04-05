"""
Agentic - Filesystem Skill
===========================
Provides safe read/write/list operations on the local filesystem.
Operations are restricted to user-accessible paths (no root/system paths).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from skills.base import SkillBase
from utils.logger import build_logger

log = build_logger("agentic.skill.filesystem")

_BLOCKED = {"/etc", "/bin", "/sbin", "/usr/bin", "/sys", "/proc"}


def _safe_path(raw: str) -> Path:
    p = Path(raw).expanduser().resolve()
    for blocked in _BLOCKED:
        if str(p).startswith(blocked):
            raise PermissionError(f"Access to {p} is not allowed")
    return p


class ReadFileSkill(SkillBase):
    name = "read_file"
    description = "Read the contents of a text file from the local filesystem."
    parameters = {
        "path": {"type": "string", "description": "Absolute or ~ path to the file"},
        "max_chars": {"type": "integer", "description": "Max characters to return (default 4000)"},
    }
    required = ["path"]
    tags = ["filesystem"]

    async def execute(self, path: str, max_chars: int = 4000) -> str:
        p = _safe_path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        if not p.is_file():
            raise ValueError(f"Not a file: {p}")
        text = p.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... [truncated at {max_chars} chars]"
        return text


class WriteFileSkill(SkillBase):
    name = "write_file"
    description = "Write text content to a file. Creates the file if it does not exist."
    parameters = {
        "path": {"type": "string", "description": "File path to write to"},
        "content": {"type": "string", "description": "Text content to write"},
        "append": {"type": "boolean", "description": "Append instead of overwrite (default false)"},
    }
    required = ["path", "content"]
    tags = ["filesystem"]

    async def execute(self, path: str, content: str, append: bool = False) -> str:
        p = _safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if append:
            with p.open("a", encoding="utf-8") as fh:
                fh.write(content)
        else:
            p.write_text(content, encoding="utf-8")
        return f"Written {len(content)} chars to {p}"


class ListDirSkill(SkillBase):
    name = "list_directory"
    description = "List files and subdirectories in a directory."
    parameters = {
        "path": {"type": "string", "description": "Directory path to list"},
        "recursive": {"type": "boolean", "description": "List recursively (default false)"},
        "max_items": {"type": "integer", "description": "Max items to return (default 100)"},
    }
    required = ["path"]
    tags = ["filesystem"]

    async def execute(
        self, path: str, recursive: bool = False, max_items: int = 100
    ) -> list[str]:
        p = _safe_path(path)
        if not p.is_dir():
            raise ValueError(f"Not a directory: {p}")
        if recursive:
            items = [str(f) for f in p.rglob("*")]
        else:
            items = [str(f) for f in p.iterdir()]
        return sorted(items)[:max_items]


def register_all() -> None:
    ReadFileSkill.register()
    WriteFileSkill.register()
    ListDirSkill.register()
