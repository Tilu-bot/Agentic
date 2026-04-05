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
  Two formats are accepted so the model can choose the clearest expression:

  Format A – inline marker (simple args):
    @@SKILL:<name> <json-args>@@

  Format B – block marker (complex/nested args, inspired by structured
    tool-use formats used in modern agent SDKs):
    <skill_call>{"name": "<name>", "args": <json-args>}</skill_call>

  The inline parser uses brace-depth tracking instead of a greedy/non-greedy
  regex so that nested JSON objects (e.g. args containing sub-dicts) are
  parsed correctly.  The old .*? approach stopped at the first closing brace
  and silently lost nested args.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.memory_lattice import FluidEntry
from model.gemma_nexus import get_assistant_role
from utils.config import cfg

_SYSTEM_TEMPLATE = """\
You are Agentic, a multi-task AI assistant powered by the Reactive Cortex Architecture.
You think carefully, act step-by-step, and use available skills when needed.

{skills_block}

{memory_block}

== Skill Invocation Syntax ==
Choose whichever format is clearest for the skill call:

  Format A (inline, for simple arguments):
    @@SKILL:<skill_name> <json_args>@@
  Example:
    @@SKILL:read_file {{"path": "/home/user/notes.txt"}}@@

  Format B (block, preferred for complex or nested arguments):
    <skill_call>{{"name": "<skill_name>", "args": <json_args>}}</skill_call>
  Example:
    <skill_call>{{"name": "run_python", "args": {{"code": "print(2+2)"}}}}</skill_call>

Only invoke skills when necessary. You may invoke multiple skills in one response.
Wait for skill results before concluding your answer.

== Core Principles ==
- Be honest about what you know and don't know.
- Break complex tasks into clear steps.
- For multi-step tasks, explain your plan before executing.
- Cite skills used in your final response.
"""

# XML-style block marker constants
_BLOCK_OPEN  = "<skill_call>"
_BLOCK_CLOSE = "</skill_call>"

# Native tool-call formats emitted by models when tools= is passed to apply_chat_template.
# Qwen 2.5 / Llama 3.1 use XML-style <tool_call> tags; Mistral uses a JSON array prefix.
_TOOL_CALL_OPEN  = "<tool_call>"
_TOOL_CALL_CLOSE = "</tool_call>"
_MISTRAL_TOOL_CALLS_PREFIX = "[TOOL_CALLS]"

# Maximum characters to include from a skill's argument dict in the observation
# message.  Keeps the context window reasonable when args contain large payloads.
_ARG_SUMMARY_MAX_CHARS = 120


@dataclass
class SkillInvocation:
    skill_name: str
    args: dict[str, Any]
    raw: str


def _extract_json_object(text: str, start: int) -> tuple[str, int] | None:
    """
    Extract a complete JSON object from *text* beginning at *start*.

    Walks character-by-character tracking brace depth and string state so
    that nested objects (e.g. {"outer": {"inner": 1}}) are captured in
    full.  Returns (json_string, exclusive_end_index) on success or None
    if no complete object is found.
    """
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    in_string = False
    escape_next = False
    i = start
    while i < len(text):
        ch = text[i]
        if escape_next:
            escape_next = False
        elif ch == "\\" and in_string:
            escape_next = True
        elif ch == '"':
            in_string = not in_string
        elif not in_string:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1], i + 1
        i += 1
    return None


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
        """
        Parse all skill invocations from an assistant response.

        Handles both inline (@@SKILL:...@@) and block (<skill_call>...</skill_call>)
        formats.  Inline args are parsed with a brace-depth tracker so nested
        JSON objects are correctly captured.
        """
        results: list[SkillInvocation] = []

        # ── Format A: @@SKILL:<name> {...}@@ ──────────────────────────
        i = 0
        inline_marker = "@@SKILL:"
        while i < len(text):
            pos = text.find(inline_marker, i)
            if pos == -1:
                break

            name_start = pos + len(inline_marker)
            # Collect the skill name (runs until whitespace or '{')
            name_end = name_start
            while name_end < len(text) and text[name_end] not in (" ", "\t", "\n", "{"):
                name_end += 1
            skill_name = text[name_start:name_end]

            # Require a valid Python identifier as the skill name
            if not skill_name or not skill_name.isidentifier():
                i = pos + 1
                continue

            # Skip optional whitespace before the JSON object
            j = name_end
            while j < len(text) and text[j] in (" ", "\t", "\n"):
                j += 1

            extracted = _extract_json_object(text, j)
            if extracted is None:
                i = pos + 1
                continue
            json_str, end_pos = extracted

            # Expect the closing @@ immediately after the JSON object
            if text[end_pos : end_pos + 2] != "@@":
                i = pos + 1
                continue

            raw = text[pos : end_pos + 2]
            try:
                args = json.loads(json_str)
            except json.JSONDecodeError:
                args = {"raw": json_str}

            results.append(SkillInvocation(skill_name=skill_name, args=args, raw=raw))
            i = end_pos + 2

        # ── Format B: <skill_call>{"name": "...", "args": {...}}</skill_call> ──
        # Inspired by structured tool-use formats in modern agent SDKs:
        # the outer object carries the name and args as distinct keys so the
        # JSON is self-describing and easier for models to emit correctly.
        j = 0
        while j < len(text):
            open_pos = text.find(_BLOCK_OPEN, j)
            if open_pos == -1:
                break
            content_start = open_pos + len(_BLOCK_OPEN)
            close_pos = text.find(_BLOCK_CLOSE, content_start)
            if close_pos == -1:
                break

            raw_content = text[content_start:close_pos].strip()
            raw = text[open_pos : close_pos + len(_BLOCK_CLOSE)]

            try:
                obj = json.loads(raw_content)
                skill_name = obj.get("name", "")
                # Accept either "args" or "arguments" as the param key
                args = obj.get("args", obj.get("arguments", {}))
                if skill_name and isinstance(args, dict):
                    results.append(
                        SkillInvocation(skill_name=skill_name, args=args, raw=raw)
                    )
            except (json.JSONDecodeError, AttributeError):
                pass

            j = close_pos + len(_BLOCK_CLOSE)

        # ── Format C: <tool_call>{"name": "...", "arguments": {...}}</tool_call> ──
        # Emitted by Qwen 2.5, Llama 3.1+, and other models when native tool
        # calling is enabled via apply_chat_template(tools=...).  Uses "arguments"
        # as the key (OpenAI convention).
        k = 0
        while k < len(text):
            open_pos = text.find(_TOOL_CALL_OPEN, k)
            if open_pos == -1:
                break
            content_start = open_pos + len(_TOOL_CALL_OPEN)
            close_pos = text.find(_TOOL_CALL_CLOSE, content_start)
            if close_pos == -1:
                break

            raw_content = text[content_start:close_pos].strip()
            raw = text[open_pos : close_pos + len(_TOOL_CALL_CLOSE)]

            try:
                obj = json.loads(raw_content)
                skill_name = obj.get("name", "")
                args = obj.get("arguments", obj.get("args", {}))
                if skill_name and isinstance(args, dict):
                    results.append(
                        SkillInvocation(skill_name=skill_name, args=args, raw=raw)
                    )
            except (json.JSONDecodeError, AttributeError):
                pass

            k = close_pos + len(_TOOL_CALL_CLOSE)

        # ── Format D: [TOOL_CALLS] [{"name": "...", "arguments": {...}}, ...] ──
        # Emitted by Mistral-Instruct models when tool calling is enabled.
        # The prefix is followed by a JSON array of tool-call objects.
        tc_pos = text.find(_MISTRAL_TOOL_CALLS_PREFIX)
        if tc_pos != -1:
            array_start = text.find("[", tc_pos + len(_MISTRAL_TOOL_CALLS_PREFIX))
            if array_start != -1:
                # Walk to find the matching closing bracket
                depth = 0
                in_string = False
                escape_next = False
                m = array_start
                while m < len(text):
                    ch = text[m]
                    if escape_next:
                        escape_next = False
                    elif ch == "\\" and in_string:
                        escape_next = True
                    elif ch == '"':
                        in_string = not in_string
                    elif not in_string:
                        if ch == "[":
                            depth += 1
                        elif ch == "]":
                            depth -= 1
                            if depth == 0:
                                break
                    m += 1
                raw_array = text[array_start : m + 1]
                try:
                    calls = json.loads(raw_array)
                    if isinstance(calls, list):
                        for call in calls:
                            skill_name = call.get("name", "")
                            args = call.get("arguments", call.get("args", {}))
                            if skill_name and isinstance(args, dict):
                                results.append(
                                    SkillInvocation(
                                        skill_name=skill_name,
                                        args=args,
                                        raw=raw_array,
                                    )
                                )
                except (json.JSONDecodeError, AttributeError):
                    pass

        return results

    @staticmethod
    def format_observations(
        results: list[tuple["SkillInvocation", str, bool]],
    ) -> str:
        """
        Build a user-turn observation message from a batch of skill results.

        In the ReAct loop the model's tool-call turn is followed by this
        observation message so the model can reason over the actual skill
        outputs before producing its final answer.  The format is explicit
        and structured so the model reliably distinguishes successes from
        failures.
        """
        parts: list[str] = [
            "== Tool Results ==",
            "The following skills were executed.  Use these results to "
            "complete your response or decide whether further tool calls are "
            "needed.",
        ]
        for inv, result, success in results:
            status = "SUCCESS" if success else "ERROR"
            arg_summary = json.dumps(inv.args, ensure_ascii=False)[:_ARG_SUMMARY_MAX_CHARS]
            parts.append(
                f"\n[{status}] {inv.skill_name}({arg_summary}):\n{result}"
            )
        parts.append(
            "\nIf all necessary information has been gathered, provide your "
            "final answer now.  If you still need to call more tools, do so."
        )
        return "\n".join(parts)


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
