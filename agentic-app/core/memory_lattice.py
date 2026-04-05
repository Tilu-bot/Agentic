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

import hashlib
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
        summary = _truncate_to_sentences(combined, max_chars=600)
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
        # Use a deterministic fact_id derived from the content so that writing
        # the same (category, text) pair twice is idempotent.  The store uses
        # INSERT OR REPLACE, so the ts and confidence will be updated but no
        # duplicate row is created.  This prevents the context window from
        # filling with repeated facts across sessions.
        fact = BedrockFact(
            fact_id=_fact_id(category, text),
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

def _fact_id(category: str, text: str) -> str:
    """
    Deterministic, content-addressed fact identifier.

    Building the ID from the normalised category and text means that
    writing the same fact twice produces the same ID, which lets the
    store's INSERT OR REPLACE deduplicate naturally.
    """
    key = f"{category.strip().lower()}:{text.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]


def _truncate_to_sentences(text: str, max_chars: int = 600) -> str:
    """
    Extractive truncation that preserves sentence boundaries.

    Splits on sentence-ending punctuation and accumulates whole sentences
    until *max_chars* would be exceeded, then stops.  The result is always
    a grammatically complete prefix of the source text rather than a raw
    character slice.  This is intentionally NOT a summarizer – no
    information is reordered or generated.
    """
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
    """
    Heuristic importance score (0.0 – 1.0) for a batch of fluid entries.

    Signals considered:
      • Keyword density  – words that typically mark important content.
      • Questions        – interrogative sentences often encode user intent.
      • Code blocks      – ``` fences carry high information density.
      • Total length     – longer exchanges are usually more substantial.
      • Role balance     – user-heavy batches tend to be more information-rich
                           than pure assistant monologues.
      • Numeric content  – dates, measurements, and figures are frequently
                           recalled in later turns.

    The baseline of 0.2 ensures that every batch receives at least minimal
    priority; the cap of 1.0 prevents runaway scores.
    """
    _KEYWORDS = {
        "error", "fail", "important", "critical", "remember",
        "note", "save", "key", "must", "should", "prefer",
        "always", "never", "warning", "todo", "urgent", "issue",
        "confirm", "agree", "decision", "goal", "requirement",
    }
    score = 0.2
    total_chars = 0
    user_turns = 0
    for entry in entries:
        words = set(entry.text.lower().split())
        keyword_hits = words & _KEYWORDS
        score += len(keyword_hits) * 0.04
        total_chars += len(entry.text)
        if "?" in entry.text:
            score += 0.03
        if "```" in entry.text:
            score += 0.06
        # Simple check for numeric/date content (digits, slashes, colons)
        digit_chars = sum(1 for ch in entry.text if ch.isdigit())
        if digit_chars > 4:
            score += 0.02
        if entry.role == "user":
            user_turns += 1

    # Reward longer exchanges (more information transferred)
    if total_chars > 2000:
        score += 0.10
    elif total_chars > 500:
        score += 0.05

    # User-heavy batches carry more explicit intent
    if entries and user_turns > len(entries) // 2:
        score += 0.05

    return min(1.0, score)
