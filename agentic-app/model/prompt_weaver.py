"""
Agentic - Prompt Weaver
=======================
Constructs prompts for the Gemma model dynamically from context.

The weaver assembles:
  1. A system block: identity + skills manifest + memory context
  2. A conversation history block: fluid memory entries
  3. The current user turn

Skill invocation protocol:
  The model signals a skill call using the compact markup:
    @@SKILL:<name> <json-args>@@
  The Cortex scans assistant output for these markers and dispatches
  them to the SkillRegistry.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from core.memory_lattice import FluidEntry

SKILL_INVOKE_PATTERN = re.compile(
    r"@@SKILL:(\w+)\s+(\{.*?\})@@", re.DOTALL
)

_SYSTEM_TEMPLATE = """\
You are Agentic, a multi-task AI assistant powered by the Reactive Cortex Architecture.
You think carefully, act step-by-step, and use available skills when needed.

{skills_block}

{memory_block}

== Skill Invocation Syntax ==
To use a skill, output exactly:
  @@SKILL:<skill_name> <json_args>@@
Example:
  @@SKILL:read_file {{"path": "/home/user/notes.txt"}}@@
Only invoke skills when necessary. You may invoke multiple skills in one response.
Wait for skill results before concluding your answer.

== Core Principles ==
- Be honest about what you know and don't know.
- Break complex tasks into clear steps.
- For multi-step tasks, explain your plan before executing.
- Cite skills used in your final response.
"""


@dataclass
class SkillInvocation:
    skill_name: str
    args: dict[str, Any]
    raw: str


class PromptWeaver:
    """Builds message lists for the Gemma chat template from session context."""

    def __init__(self, skills_manifest: str) -> None:
        self._skills_manifest = skills_manifest

    def build_system(self, memory_context: str = "") -> str:
        memory_block = ""
        if memory_context.strip():
            memory_block = f"== Memory Context ==\n{memory_context}"
        return _SYSTEM_TEMPLATE.format(
            skills_block=self._skills_manifest,
            memory_block=memory_block,
        ).strip()

    def build_messages(
        self,
        fluid: list[FluidEntry],
        user_input: str,
    ) -> list[dict]:
        """
        Convert fluid memory entries + new user input into a Gemma chat
        message list (role / content pairs).
        Gemma uses "user" and "model" roles.
        """
        messages: list[dict] = []

        for entry in fluid:
            role = _map_role(entry.role)
            if role:
                messages.append({"role": role, "content": entry.text})

        messages.append({"role": "user", "content": user_input})
        return messages

    @staticmethod
    def extract_skill_calls(text: str) -> list[SkillInvocation]:
        """Parse all @@SKILL:...@@ markers from an assistant response."""
        results: list[SkillInvocation] = []
        for m in SKILL_INVOKE_PATTERN.finditer(text):
            skill_name = m.group(1)
            raw_args   = m.group(2)
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {"raw": raw_args}
            results.append(
                SkillInvocation(skill_name=skill_name, args=args, raw=m.group(0))
            )
        return results

    @staticmethod
    def inject_skill_result(text: str, invocation: SkillInvocation, result: str) -> str:
        """Replace a @@SKILL:...@@ marker with its result in the response text."""
        replacement = f"[Skill: {invocation.skill_name} → {result}]"
        return text.replace(invocation.raw, replacement, 1)


def _map_role(role: str) -> str | None:
    # Gemma instruction models use "user" and "model" as turn roles.
    mapping = {
        "user":      "user",
        "assistant": "model",
        "system":    "user",    # system turns are encoded as user turns
        "skill":     "model",   # skill results become part of model context
    }
    return mapping.get(role.lower())
