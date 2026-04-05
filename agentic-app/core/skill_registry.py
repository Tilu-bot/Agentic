"""
Agentic - Skill Registry
========================
Skills are the callable capabilities available to the Cortex.

Design:
  • Each skill is a self-describing unit with a name, description, and
    a JSON-schema for its parameters.
  • The registry is a dictionary of skill_name → Skill instances.
  • Skills are registered at startup and can be hot-loaded later.
  • The Cortex queries the registry to build the tools list embedded in
    every system prompt.
  • Skills report progress via the Signal Lattice so the UI can track
    execution without coupling to the skill implementation.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable, Coroutine

from core.signal_lattice import SigKind, lattice
from utils.logger import build_logger

log = build_logger("agentic.skill_registry")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

SkillFn = Callable[..., Coroutine[Any, Any, Any]]


@dataclass
class SkillSpec:
    """
    Self-describing skill definition.

    name        – machine identifier, used in prompts (snake_case)
    description – one-sentence human-readable description
    parameters  – JSON Schema "properties" dict for parameter documentation
    required    – list of required parameter names
    fn          – async callable that implements the skill
    tags        – optional category labels (e.g. "filesystem", "web")
    """
    name: str
    description: str
    fn: SkillFn
    parameters: dict[str, Any] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class SkillResult:
    skill_name: str
    success: bool
    output: Any
    error: str = ""
    elapsed_s: float = 0.0


# ---------------------------------------------------------------------------
# Skill Registry
# ---------------------------------------------------------------------------

class SkillRegistry:
    """
    Central registry for all Agentic skills.

    Thread-safe.  Skills are identified by their name (unique).
    The registry also handles invocation, timing, and signal emission.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._skills: dict[str, SkillSpec] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, spec: SkillSpec) -> None:
        with self._lock:
            if spec.name in self._skills:
                log.warning("Overwriting skill: %s", spec.name)
            self._skills[spec.name] = spec
        log.debug("Skill registered: %s", spec.name)

    def unregister(self, name: str) -> bool:
        with self._lock:
            return bool(self._skills.pop(name, None))

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get(self, name: str) -> SkillSpec | None:
        with self._lock:
            return self._skills.get(name)

    def all_specs(self) -> list[SkillSpec]:
        with self._lock:
            return list(self._skills.values())

    def by_tag(self, tag: str) -> list[SkillSpec]:
        with self._lock:
            return [s for s in self._skills.values() if tag in s.tags]

    def tools_manifest(self) -> str:
        """
        Return a compact text block describing all registered skills.
        This block is embedded in the system prompt so the model knows
        which skills it can request.
        """
        lines: list[str] = ["Available Skills:"]
        with self._lock:
            for spec in self._skills.values():
                param_names = ", ".join(spec.parameters.keys())
                lines.append(
                    f"  • {spec.name}({param_names}): {spec.description}"
                )
        return "\n".join(lines)

    def tools_schema(self) -> list[dict]:
        """
        Return an OpenAI-format tool schema list for all registered skills.

        This is passed to ``tokenizer.apply_chat_template(tools=...)`` for
        models that support native function/tool calling (Llama 3.1+, Qwen 2.5,
        Phi-4, Mistral-Nemo).  The schema follows the JSON-Schema ``object``
        format expected by the HuggingFace chat-template tool-use extension.
        """
        schemas: list[dict] = []
        with self._lock:
            for spec in self._skills.values():
                schemas.append({
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": {
                            "type": "object",
                            "properties": spec.parameters,
                            "required": spec.required,
                        },
                    },
                })
        return schemas

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------

    async def invoke(self, name: str, **kwargs: Any) -> SkillResult:
        """
        Invoke a registered skill by name.
        Emits SKILL_INVOKED and SKILL_RESULT / SKILL_ERROR signals.

        The configured ``skill_timeout_s`` value is enforced here so that a
        misbehaving or blocked skill cannot stall the entire ReAct loop
        indefinitely.  On timeout the skill is cancelled and a SkillResult
        with ``success=False`` is returned.
        """
        spec = self.get(name)
        if spec is None:
            msg = f"Unknown skill: {name}"
            log.error(msg)
            return SkillResult(
                skill_name=name, success=False, output=None, error=msg
            )

        lattice.emit_kind(
            SigKind.SKILL_INVOKED,
            {"skill": name, "args": kwargs},
            source="skill_registry",
        )

        from utils.config import cfg  # local import to avoid circular at module load
        timeout_s: float = cfg.get("skill_timeout_s", 30)

        t0 = time.monotonic()
        try:
            output = await asyncio.wait_for(spec.fn(**kwargs), timeout=timeout_s)
            elapsed = time.monotonic() - t0
            result = SkillResult(
                skill_name=name, success=True, output=output, elapsed_s=elapsed
            )
            lattice.emit_kind(
                SigKind.SKILL_RESULT,
                {"skill": name, "output": output, "elapsed_s": elapsed},
                source="skill_registry",
            )
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - t0
            msg = f"Skill '{name}' timed out after {timeout_s}s"
            log.warning(msg)
            result = SkillResult(
                skill_name=name,
                success=False,
                output=None,
                error=msg,
                elapsed_s=elapsed,
            )
            lattice.emit_kind(
                SigKind.SKILL_ERROR,
                {"skill": name, "error": msg},
                source="skill_registry",
            )
        except Exception as exc:
            elapsed = time.monotonic() - t0
            result = SkillResult(
                skill_name=name,
                success=False,
                output=None,
                error=str(exc),
                elapsed_s=elapsed,
            )
            lattice.emit_kind(
                SigKind.SKILL_ERROR,
                {"skill": name, "error": str(exc)},
                source="skill_registry",
            )
            log.exception("Skill %s failed: %s", name, exc)

        return result


# Module-level singleton
skill_registry = SkillRegistry()
