"""
Agentic - Memory Operations Skill
====================================
Allows the model to explicitly read from and write to the Memory Lattice.
This enables the agent to self-direct its memory: save key information
and query past knowledge without waiting for automatic crystallization.
"""
from __future__ import annotations

from typing import Any

from skills.base import SkillBase
from utils.logger import build_logger

log = build_logger("agentic.skill.memory")

# The MemoryLattice is injected at registration time by the app bootstrap
_memory_ref: Any = None


def set_memory_ref(mem: Any) -> None:
    global _memory_ref
    _memory_ref = mem


class SaveFactSkill(SkillBase):
    name = "save_fact"
    description = (
        "Persist an important fact to long-term memory (Bedrock tier). "
        "Use for preferences, key decisions, user details, etc."
    )
    parameters = {
        "category": {"type": "string", "description": "Category label (e.g. 'preference', 'context')"},
        "text": {"type": "string", "description": "The fact to remember"},
        "confidence": {"type": "number", "description": "Confidence score 0.0–1.0 (default 0.9)"},
    }
    required = ["category", "text"]
    tags = ["memory"]

    async def execute(self, category: str, text: str, confidence: float = 0.9) -> str:
        if _memory_ref is None:
            return "Memory not available."
        fact = _memory_ref.bedrock_write(category, text, confidence)
        return f"Saved fact [{category}]: {text[:100]}"


class RecallFactsSkill(SkillBase):
    name = "recall_facts"
    description = (
        "Query long-term memory (Bedrock) for stored facts. "
        "Optionally filter by category."
    )
    parameters = {
        "category": {"type": "string", "description": "Category to filter by (optional)"},
        "limit": {"type": "integer", "description": "Max facts to return (default 10)"},
    }
    required = []
    tags = ["memory"]

    async def execute(self, category: str = "", limit: int = 10) -> list[str]:
        if _memory_ref is None:
            return ["Memory not available."]
        facts = _memory_ref.bedrock_query(category=category or None, limit=limit)
        return [f"[{f.category}] {f.text}" for f in facts]


class RecallHistorySkill(SkillBase):
    name = "recall_history"
    description = (
        "Query recent compressed conversation history (Crystal tier). "
        "Returns summaries of past interactions."
    )
    parameters = {
        "limit": {"type": "integer", "description": "Max records to return (default 5)"},
    }
    required = []
    tags = ["memory"]

    async def execute(self, limit: int = 5) -> list[str]:
        if _memory_ref is None:
            return ["Memory not available."]
        records = _memory_ref.crystal_query(limit=limit)
        return [r.summary for r in records]


def register_all(memory: Any) -> None:
    set_memory_ref(memory)
    SaveFactSkill.register()
    RecallFactsSkill.register()
    RecallHistorySkill.register()
