"""
Agentic - Memory Lattice
========================
Three-tier memory system:

  FLUID  → working context, held in RAM, bounded by a sliding window.
  CRYSTAL → compressed episodic records, persisted to SQLite.
  BEDROCK → semantic summaries (key facts) persisted to SQLite.

Access pattern:
  - Fluid: read/write every turn (O(1))
  - Crystal: append on fluid overflow, query by recency/tags (O(log n))
  - Bedrock: updated after deliberation cycles, queried for domain facts

Memory is *not* a flat list of messages – it is a typed lattice where
each tier has its own data structure and compaction rules.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass
from threading import Lock
from typing import Any

from state.store import Store
from utils.logger import build_logger

log = build_logger("agentic.memory")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class FluidEntry:
    role: str        # "user" | "assistant" | "system" | "skill"
    text: str
    ts: float = 0.0
    tags: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.ts == 0.0:
            self.ts = time.time()
        if self.tags is None:
            self.tags = []


@dataclass
class CrystalRecord:
    record_id: str
    session_id: str
    summary: str
    tags: list[str]
    ts: float
    importance: float   # 0.0 – 1.0


@dataclass
class BedrockFact:
    fact_id: str
    category: str       # e.g. "preference", "capability", "context"
    text: str
    confidence: float   # 0.0 – 1.0
    ts: float


# ---------------------------------------------------------------------------
# Memory Lattice
# ---------------------------------------------------------------------------

class MemoryLattice:
    """
    Manages all three memory tiers for a session.
    Thread-safe for concurrent reads/writes from UI and worker threads.
    """

    def __init__(
        self,
        store: Store,
        session_id: str,
        fluid_limit: int = 20,
    ) -> None:
        self._store = store
        self._session_id = session_id
        self._fluid_limit = fluid_limit
        self._lock = Lock()
        self._fluid: list[FluidEntry] = []

    # ------------------------------------------------------------------
    # FLUID tier – in-memory sliding window
    # ------------------------------------------------------------------

    def fluid_write(self, role: str, text: str, tags: list[str] | None = None) -> None:
        entry = FluidEntry(role=role, text=text, tags=tags or [])
        with self._lock:
            self._fluid.append(entry)
            if len(self._fluid) > self._fluid_limit:
                overflow = self._fluid[: self._fluid_limit // 2]
                self._fluid = self._fluid[self._fluid_limit // 2 :]
                self._crystallize(overflow)

    def fluid_read(self) -> list[FluidEntry]:
        with self._lock:
            return list(self._fluid)

    def fluid_clear(self) -> None:
        with self._lock:
            if self._fluid:
                self._crystallize(self._fluid)
            self._fluid = []

    # ------------------------------------------------------------------
    # CRYSTAL tier – compressed episodic records
    # ------------------------------------------------------------------

    def _crystallize(self, entries: list[FluidEntry]) -> None:
        """Compress a batch of fluid entries into a crystal record."""
        if not entries:
            return
        combined = "\n".join(
            f"[{e.role.upper()}] {e.text[:400]}" for e in entries
        )
        tags: list[str] = list({t for e in entries for t in e.tags})
        summary = _summarize_text(combined, max_chars=600)
        record = CrystalRecord(
            record_id=uuid.uuid4().hex,
            session_id=self._session_id,
            summary=summary,
            tags=tags,
            ts=time.time(),
            importance=_score_importance(entries),
        )
        self._store.crystal_insert(record)
        log.debug("Crystallized %d entries → record %s", len(entries), record.record_id)

    def crystal_query(
        self,
        limit: int = 10,
        tags: list[str] | None = None,
    ) -> list[CrystalRecord]:
        return self._store.crystal_query(self._session_id, limit=limit, tags=tags)

    # ------------------------------------------------------------------
    # BEDROCK tier – semantic facts
    # ------------------------------------------------------------------

    def bedrock_write(
        self, category: str, text: str, confidence: float = 0.8
    ) -> BedrockFact:
        fact = BedrockFact(
            fact_id=uuid.uuid4().hex,
            category=category,
            text=text,
            confidence=confidence,
            ts=time.time(),
        )
        self._store.bedrock_insert(fact)
        return fact

    def bedrock_query(
        self, category: str | None = None, limit: int = 20
    ) -> list[BedrockFact]:
        return self._store.bedrock_query(category=category, limit=limit)

    # ------------------------------------------------------------------
    # Context assembly – prepare prompt context from all tiers
    # ------------------------------------------------------------------

    def assemble_context(
        self,
        include_crystal: int = 5,
        include_bedrock: int = 10,
    ) -> str:
        """
        Build a text block summarising relevant memory for the next
        deliberation cycle.
        """
        parts: list[str] = []

        bedrock_facts = self.bedrock_query(limit=include_bedrock)
        if bedrock_facts:
            parts.append("=== Known Facts ===")
            for f in bedrock_facts:
                parts.append(f"[{f.category}] {f.text}")

        crystal_records = self.crystal_query(limit=include_crystal)
        if crystal_records:
            parts.append("\n=== Past Context ===")
            for r in sorted(crystal_records, key=lambda x: x.ts):
                parts.append(f"• {r.summary}")

        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _summarize_text(text: str, max_chars: int = 600) -> str:
    """Very lightweight extractive summarizer (no LLM call)."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    result: list[str] = []
    total = 0
    for s in sentences:
        if total + len(s) <= max_chars:
            result.append(s)
            total += len(s)
        else:
            break
    return " ".join(result) if result else text[:max_chars]


def _score_importance(entries: list[FluidEntry]) -> float:
    """Heuristic importance score for a batch of fluid entries."""
    keywords = {
        "error", "fail", "important", "critical", "remember",
        "note", "save", "key", "must", "should",
    }
    score = 0.3  # baseline
    for e in entries:
        words = set(e.text.lower().split())
        hits = words & keywords
        score += len(hits) * 0.05
    return min(1.0, score)
