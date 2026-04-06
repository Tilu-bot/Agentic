"""
Tests for model/prompt_weaver.py – skill call extraction for all 4 formats.
"""
import pytest
from model.prompt_weaver import PromptWeaver, SkillInvocation


def extract(text: str) -> list[SkillInvocation]:
    return PromptWeaver.extract_skill_calls(text)


# ---------------------------------------------------------------------------
# Format A – @@SKILL:<name> {...}@@
# ---------------------------------------------------------------------------

class TestFormatA:

    def test_simple_args(self):
        text = '@@SKILL:read_file {"path": "/tmp/notes.txt"}@@'
        calls = extract(text)
        assert len(calls) == 1
        assert calls[0].skill_name == "read_file"
        assert calls[0].args == {"path": "/tmp/notes.txt"}

    def test_nested_json(self):
        text = '@@SKILL:run_code {"code": "print(1)", "env": {"lang": "python"}}@@'
        calls = extract(text)
        assert len(calls) == 1
        assert calls[0].args["env"] == {"lang": "python"}

    def test_multiple_calls(self):
        text = (
            '@@SKILL:fetch {"url": "https://example.com"}@@ '
            '@@SKILL:save {"path": "/tmp/out.txt", "data": "hello"}@@'
        )
        calls = extract(text)
        assert len(calls) == 2
        assert calls[0].skill_name == "fetch"
        assert calls[1].skill_name == "save"

    def test_invalid_skill_name_skipped(self):
        text = '@@SKILL:123bad {"x": 1}@@'
        calls = extract(text)
        assert calls == []

    def test_missing_closing_at_signs_skipped(self):
        text = '@@SKILL:read_file {"path": "/tmp/f.txt"}'
        calls = extract(text)
        assert calls == []


# ---------------------------------------------------------------------------
# Format B – <skill_call>{"name": "...", "args": {...}}</skill_call>
# ---------------------------------------------------------------------------

class TestFormatB:

    def test_simple(self):
        text = '<skill_call>{"name": "list_dir", "args": {"path": "/home"}}</skill_call>'
        calls = extract(text)
        assert len(calls) == 1
        assert calls[0].skill_name == "list_dir"
        assert calls[0].args == {"path": "/home"}

    def test_arguments_key_alias(self):
        text = '<skill_call>{"name": "fetch", "arguments": {"url": "http://x.com"}}</skill_call>'
        calls = extract(text)
        assert len(calls) == 1
        assert calls[0].args == {"url": "http://x.com"}

    def test_invalid_json_skipped(self):
        text = "<skill_call>not json</skill_call>"
        calls = extract(text)
        assert calls == []

    def test_missing_name_skipped(self):
        text = '<skill_call>{"args": {"x": 1}}</skill_call>'
        calls = extract(text)
        assert calls == []


# ---------------------------------------------------------------------------
# Format C – <tool_call>{"name": "...", "arguments": {...}}</tool_call>
# ---------------------------------------------------------------------------

class TestFormatC:

    def test_simple(self):
        text = '<tool_call>{"name": "search", "arguments": {"q": "test"}}</tool_call>'
        calls = extract(text)
        assert len(calls) == 1
        assert calls[0].skill_name == "search"
        assert calls[0].args == {"q": "test"}

    def test_args_key_alias(self):
        text = '<tool_call>{"name": "compute", "args": {"expr": "1+1"}}</tool_call>'
        calls = extract(text)
        assert len(calls) == 1
        assert calls[0].args == {"expr": "1+1"}


# ---------------------------------------------------------------------------
# Format D – [TOOL_CALLS] [{"name": "...", "arguments": {...}}, ...]
# ---------------------------------------------------------------------------

class TestFormatD:

    def test_single_tool_call(self):
        text = '[TOOL_CALLS] [{"name": "ping", "arguments": {"host": "localhost"}}]'
        calls = extract(text)
        # Format D results may overlap with earlier formats; check at least one.
        ping = [c for c in calls if c.skill_name == "ping"]
        assert len(ping) >= 1
        assert ping[0].args == {"host": "localhost"}

    def test_multiple_tool_calls(self):
        text = (
            '[TOOL_CALLS] ['
            '{"name": "tool_a", "arguments": {"x": 1}}, '
            '{"name": "tool_b", "arguments": {"y": 2}}'
            ']'
        )
        calls = extract(text)
        names = [c.skill_name for c in calls]
        assert "tool_a" in names
        assert "tool_b" in names


# ---------------------------------------------------------------------------
# Mixed / edge cases
# ---------------------------------------------------------------------------

class TestMixed:

    def test_empty_text(self):
        assert extract("") == []

    def test_no_markers(self):
        assert extract("Just a plain response.") == []

    def test_format_a_and_b_in_same_response(self):
        text = (
            '@@SKILL:read_file {"path": "/a.txt"}@@ '
            '<skill_call>{"name": "write_file", "args": {"path": "/b.txt", "data": "hi"}}</skill_call>'
        )
        calls = extract(text)
        names = [c.skill_name for c in calls]
        assert "read_file" in names
        assert "write_file" in names
