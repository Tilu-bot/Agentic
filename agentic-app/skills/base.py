"""
Agentic - Base Skill Interface
================================
All skills must implement SkillBase.  The register() classmethod
provides a convenient decorator-style registration with the global
SkillRegistry.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.skill_registry import SkillSpec, skill_registry


class SkillBase(ABC):
    """Abstract base for all Agentic skills."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}
    required: list[str] = []
    tags: list[str] = []

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        ...

    @classmethod
    def register(cls) -> None:
        instance = cls()
        spec = SkillSpec(
            name=cls.name,
            description=cls.description,
            fn=instance.execute,
            parameters=cls.parameters,
            required=cls.required,
            tags=cls.tags,
        )
        skill_registry.register(spec)
