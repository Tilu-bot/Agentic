"""
Agentic - Prompt Weaver
=======================
Constructs prompts for any instruction-tuned model dynamically from context.

The weaver assembles:
  1. A system block: identity + skills manifest + memory context
  2. A conversation history block: fluid memory entries
  3. The current user turn

Role mapping:
  HuggingFace chat templates differ by model family.  Gemma uses "model"
  for the assistant turn; all other families (Llama, Mistral, Phi, Qwen, …)
  use "assistant".  _map_role() reads the active model_id from config and
  returns the correct role string so apply_chat_template() works for any
  supported model.

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
from model.gemma_nexus import get_assistant_role
from utils.config import cfg

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
    """Builds message lists for any HuggingFace chat model from session context."""

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
        Convert fluid memory entries + new user input into a chat message list
        (role / content pairs) compatible with the active model's chat template.

        The assistant-turn role ("model" for Gemma, "assistant" for all other
        families) is determined by reading the active model_id from config so
        apply_chat_template() receives the correct role string.
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
    """
    Map an internal Agentic role to the chat-template role expected by the
    active model.

    Gemma instruction models use "model" for the assistant turn; all other
    HuggingFace model families (Llama, Mistral, Phi, Qwen, …) use "assistant".
    The correct string is resolved at call-time from the active config so that
    switching the model_id in Settings immediately affects new messages.
    """
    model_id = cfg.get("model_id", "")
    asst_role = get_assistant_role(model_id)

    mapping = {
        "user":      "user",
        "assistant": asst_role,
        "system":    "user",      # system turns are encoded as user turns
        "skill":     asst_role,   # skill results become part of assistant context
    }
    return mapping.get(role.lower())
