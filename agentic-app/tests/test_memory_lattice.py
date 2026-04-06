"""
Tests for core/memory_lattice.py – fluid read/write, eviction, crystal,
bedrock deduplication, context assembly, and the extractive summariser.
"""
import time

import pytest
from unittest.mock import MagicMock, call as mock_call

from core.memory_lattice import (
    MemoryLattice,
    FluidEntry,
    CrystalRecord,
    BedrockFact,
    _extractive_summarize,
    _score_importance,
    _fact_id,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(session_id: str = "test-session"):
    """Return a minimal mock Store that satisfies MemoryLattice's interface."""
    store = MagicMock()
    store.fluid_restore.return_value = []
    store.crystal_query.return_value = []
    store.bedrock_query.return_value = []
    return store


def _make_lattice(fluid_limit: int = 5, session_id: str = "sess-1"):
    store = _make_store(session_id)
    return MemoryLattice(store, session_id, fluid_limit=fluid_limit), store


# ---------------------------------------------------------------------------
# FluidEntry
# ---------------------------------------------------------------------------

class TestFluidEntry:

    def test_auto_timestamp(self):
        before = time.time()
        e = FluidEntry(role="user", text="hello")
        after = time.time()
        assert before <= e.ts <= after

    def test_auto_entry_id(self):
        e1 = FluidEntry(role="user", text="a")
        e2 = FluidEntry(role="user", text="b")
        assert e1.entry_id != e2.entry_id
        assert len(e1.entry_id) == 32  # uuid4().hex

    def test_explicit_entry_id(self):
        e = FluidEntry(role="user", text="x", entry_id="fixed-id")
        assert e.entry_id == "fixed-id"


# ---------------------------------------------------------------------------
# MemoryLattice – fluid tier
# ---------------------------------------------------------------------------

class TestFluidTier:

    def test_write_and_read(self):
        lattice, _ = _make_lattice()
        lattice.fluid_write("user", "hello")
        lattice.fluid_write("assistant", "world")
        entries = lattice.fluid_read()
        assert len(entries) == 2
        assert entries[0].role == "user"
        assert entries[0].text == "hello"
        assert entries[1].role == "assistant"

    def test_write_persists_to_store(self):
        lattice, store = _make_lattice()
        lattice.fluid_write("user", "test message")
        store.fluid_insert.assert_called_once()
        kwargs = store.fluid_insert.call_args.kwargs
        assert kwargs["role"] == "user"
        assert kwargs["text"] == "test message"
        assert kwargs["session_id"] == "sess-1"

    def test_eviction_on_overflow(self):
        lattice, store = _make_lattice(fluid_limit=3)
        for i in range(4):
            lattice.fluid_write("user", f"message {i}")
        # After 4 writes with limit=3, eviction must have occurred.
        # fluid has at most fluid_limit entries.
        assert len(lattice.fluid_read()) <= 3
        store.crystal_insert.assert_called()

    def test_fluid_clear_calls_store(self):
        lattice, store = _make_lattice()
        lattice.fluid_write("user", "hi")
        lattice.fluid_clear()
        assert lattice.fluid_read() == []
        store.fluid_clear.assert_called_with("sess-1")

    def test_restore_fluid_from_store(self):
        store = _make_store()
        ts = time.time()
        store.fluid_restore.return_value = [
            {"role": "user", "text": "restored", "tags": [], "ts": ts, "entry_id": "abc123"},
        ]
        lattice = MemoryLattice(store, "sess-1", fluid_limit=20)
        entries = lattice.fluid_read()
        assert len(entries) == 1
        assert entries[0].text == "restored"
        assert entries[0].entry_id == "abc123"

    def test_tags_passed_through(self):
        lattice, store = _make_lattice()
        lattice.fluid_write("user", "important note", tags=["urgent"])
        kwargs = store.fluid_insert.call_args.kwargs
        assert kwargs["tags"] == ["urgent"]


# ---------------------------------------------------------------------------
# MemoryLattice – bedrock tier
# ---------------------------------------------------------------------------

class TestBedrockTier:

    def test_write_and_query(self):
        lattice, store = _make_lattice()
        fact = lattice.bedrock_write("preference", "prefers dark mode", confidence=0.9)
        assert fact.category == "preference"
        assert fact.text == "prefers dark mode"
        store.bedrock_insert.assert_called_once()

    def test_fact_id_deterministic(self):
        id1 = _fact_id("preference", "dark mode")
        id2 = _fact_id("preference", "dark mode")
        assert id1 == id2

    def test_fact_id_differs_on_different_content(self):
        assert _fact_id("preference", "dark mode") != _fact_id("preference", "light mode")

    def test_fact_id_normalises_whitespace(self):
        id1 = _fact_id("  preference  ", "dark mode  ")
        id2 = _fact_id("preference", "dark mode")
        assert id1 == id2


# ---------------------------------------------------------------------------
# _score_importance
# ---------------------------------------------------------------------------

class TestScoreImportance:

    def test_baseline(self):
        entries = [FluidEntry(role="user", text="hello")]
        score = _score_importance(entries)
        assert 0.0 <= score <= 1.0

    def test_keyword_raises_score(self):
        plain   = [FluidEntry(role="user", text="what time is it")]
        keyword = [FluidEntry(role="user", text="critical error must fix always")]
        assert _score_importance(keyword) > _score_importance(plain)

    def test_code_block_bonus(self):
        code = [FluidEntry(role="assistant", text="```python\nprint(1)\n```")]
        plain = [FluidEntry(role="assistant", text="just text")]
        assert _score_importance(code) > _score_importance(plain)

    def test_capped_at_one(self):
        many = [FluidEntry(role="user", text=" ".join(["critical error must always never"] * 100))]
        assert _score_importance(many) <= 1.0


# ---------------------------------------------------------------------------
# _extractive_summarize
# ---------------------------------------------------------------------------

class TestExtractiveSummarize:

    def test_output_within_max_chars(self):
        text = "This is sentence one. This is sentence two. This is sentence three."
        result = _extractive_summarize(text, max_chars=60)
        assert len(result) <= 60

    def test_empty_input(self):
        result = _extractive_summarize("", max_chars=100)
        assert isinstance(result, str)

    def test_short_text_unchanged(self):
        text = "Short text."
        result = _extractive_summarize(text, max_chars=500)
        assert "Short text" in result

    def test_keyword_sentence_preferred(self):
        text = (
            "The sky is blue. "
            "Critical error: the system must be fixed immediately! "
            "The grass is green."
        )
        result = _extractive_summarize(text, max_chars=80)
        assert "Critical error" in result or "must be fixed" in result

    def test_preserves_original_order(self):
        text = "Alpha sentence. Beta sentence. Gamma sentence."
        result = _extractive_summarize(text, max_chars=200)
        parts = [p for p in ["Alpha", "Beta", "Gamma"] if p in result]
        # Whatever subset is chosen, order must be preserved.
        for i in range(len(parts) - 1):
            assert result.index(parts[i]) < result.index(parts[i + 1])


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

class TestContextAssembly:

    def test_empty_memory_returns_empty_string(self):
        lattice, _ = _make_lattice()
        ctx = lattice.assemble_context()
        assert ctx == ""

    def test_bedrock_facts_included(self):
        lattice, store = _make_lattice()
        store.bedrock_query.return_value = [
            BedrockFact(
                fact_id="abc",
                category="pref",
                text="user likes Python",
                confidence=0.9,
                ts=time.time(),
            )
        ]
        ctx = lattice.assemble_context()
        assert "user likes Python" in ctx

    def test_crystal_records_included(self):
        lattice, store = _make_lattice()
        store.crystal_query.return_value = [
            CrystalRecord(
                record_id="r1",
                session_id="sess-1",
                summary="We discussed project Alpha.",
                tags=[],
                ts=time.time(),
                importance=0.5,
            )
        ]
        ctx = lattice.assemble_context()
        assert "project Alpha" in ctx
