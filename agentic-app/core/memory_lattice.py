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
from dataclasses import asdict, dataclass, field
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
    tags: list[str] = field(default_factory=list)
    entry_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self) -> None:
        if self.ts == 0.0:
            self.ts = time.time()


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
        self._restore_fluid()

    # ------------------------------------------------------------------
    # FLUID tier – in-memory sliding window
    # ------------------------------------------------------------------

    def fluid_write(self, role: str, text: str, tags: list[str] | None = None) -> None:
        entry = FluidEntry(role=role, text=text, tags=tags or [])
        with self._lock:
            self._fluid.append(entry)
            # Persist immediately so a crash doesn't lose this turn.
            self._store.fluid_insert(
                entry_id=entry.entry_id,
                session_id=self._session_id,
                role=entry.role,
                text=entry.text,
                tags=entry.tags,
                ts=entry.ts,
            )
            if len(self._fluid) > self._fluid_limit:
                self._evict_to_crystal()

    def fluid_read(self) -> list[FluidEntry]:
        with self._lock:
            return list(self._fluid)

    def fluid_clear(self) -> None:
        with self._lock:
            if self._fluid:
                self._crystallize(self._fluid)
            self._fluid = []
            self._store.fluid_clear(self._session_id)

    def _restore_fluid(self) -> None:
        """Reload any persisted fluid entries from the previous session run."""
        rows = self._store.fluid_restore(self._session_id)
        for r in rows:
            entry = FluidEntry(
                role=r["role"],
                text=r["text"],
                tags=r["tags"],
                ts=r["ts"],
                entry_id=r["entry_id"],
            )
            self._fluid.append(entry)
        if rows:
            log.info(
                "Restored %d fluid entries for session %s",
                len(rows), self._session_id[:8],
            )

    def _evict_to_crystal(self) -> None:
        """
        Evict the least-valuable half of the fluid window to the Crystal tier.

        Rather than always discarding the *oldest* entries (pure FIFO), each
        entry is ranked by a combined keep-score that balances recency with
        importance.  Recent *and* high-importance entries are retained; old
        *and* low-importance ones are crystallised first.

        keep_score = 0.6 × recency_rank + 0.4 × importance_score

        where recency_rank is 0.0 for the oldest entry and 1.0 for the newest.
        This means a very important old turn is kept over a trivial recent one,
        but recency still outweighs importance 60/40 so the conversational flow
        is preserved.
        """
        n = len(self._fluid)
        evict_count = n - (self._fluid_limit // 2)
        if evict_count <= 0:
            return

        scored: list[tuple[float, int, FluidEntry]] = []
        for i, entry in enumerate(self._fluid):
            # When there's only one entry, it is both oldest and newest;
            # treat its recency as 1.0 so it is never penalised.
            recency    = (i / (n - 1)) if n > 1 else 1.0
            importance = _score_importance([entry])  # 0.0 – 1.0
            keep_score = _EVICT_RECENCY_WEIGHT * recency + _EVICT_IMPORTANCE_WEIGHT * importance
            scored.append((keep_score, i, entry))

        # Sort ascending: lowest keep_score → evicted first
        scored.sort(key=lambda x: x[0])
        evict_set = {idx for _, idx, _ in scored[:evict_count]}

        to_evict   = [e for i, e in enumerate(self._fluid) if i in evict_set]
        self._fluid = [e for i, e in enumerate(self._fluid) if i not in evict_set]
        self._crystallize(to_evict)
        # Remove the now-crystallised entries from the persistence layer.
        self._store.fluid_delete_entries([e.entry_id for e in to_evict])

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
        summary = _extractive_summarize(combined, max_chars=600)
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
        query: str = "",
    ) -> str:
        """
        Build a text block summarising relevant memory for the next
        deliberation cycle.

        When *query* is provided, Bedrock facts are ranked by keyword-overlap
        relevance to the query rather than purely by recency.  A larger
        candidate pool (2× include_bedrock) is fetched and then trimmed after
        scoring, so the most contextually pertinent facts appear in the prompt.
        """
        parts: list[str] = []

        # Fetch a larger pool when relevance ranking is active so the top-k
        # slice is chosen from a meaningful distribution.
        candidate_limit = include_bedrock * 2 if query else include_bedrock
        bedrock_facts = self.bedrock_query(limit=candidate_limit)
        if bedrock_facts:
            if query:
                bedrock_facts = sorted(
                    bedrock_facts,
                    key=lambda f: _score_relevance(query, f.text),
                    reverse=True,
                )[:include_bedrock]
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

# Weights for the keep-score formula used in _evict_to_crystal().
# Keep-score = _EVICT_RECENCY_WEIGHT × recency + _EVICT_IMPORTANCE_WEIGHT × importance
# Recency is weighted slightly higher than importance (60/40) so that normal
# conversational flow is preserved while still keeping high-value old turns.
_EVICT_RECENCY_WEIGHT    = 0.6
_EVICT_IMPORTANCE_WEIGHT = 0.4

# Shared keyword set used by both _score_importance and _extractive_summarize.
_IMPORTANCE_KEYWORDS: frozenset[str] = frozenset({
    "error", "fail", "important", "critical", "remember",
    "note", "save", "key", "must", "should", "prefer",
    "always", "never", "warning", "todo", "urgent", "issue",
    "confirm", "agree", "decision", "goal", "requirement",
})


def _fact_id(category: str, text: str) -> str:
    """
    Deterministic, content-addressed fact identifier.

    Building the ID from the normalised category and text means that
    writing the same fact twice produces the same ID, which lets the
    store's INSERT OR REPLACE deduplicate naturally.
    """
    key = f"{category.strip().lower()}:{text.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]


def _extractive_summarize(text: str, max_chars: int = 600) -> str:
    """
    Importance-scored extractive summarizer.

    Splits *text* into sentences and scores each one on three signals:
      • Keyword density  – sentences containing important words score higher.
      • Position weight  – first and last sentences are given a bonus because
                           they tend to carry the topic statement and conclusion.
      • Content bonuses  – code fences (triple backtick) and questions add bonus points
                           because they encode high-information content.

    The top-scoring sentences are selected greedily (largest score first)
    until *max_chars* would be exceeded.  Selected sentences are then
    re-emitted in their *original order* so the summary reads naturally.

    This replaces a pure character-truncation approach and produces
    higher-quality crystal records, especially for long mixed conversations.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    if not sentences:
        return text[:max_chars]

    n = len(sentences)

    def _sentence_score(idx: int, s: str) -> float:
        words = [w.strip(".,!?;:'\"()[]{}").lower() for w in s.split()]
        kw_hits = sum(1 for w in words if w in _IMPORTANCE_KEYWORDS)
        kw_score = kw_hits / max(len(words), 1)
        # First and last sentences carry the topic / conclusion.
        pos_score = 1.0 if idx == 0 else (0.8 if idx == n - 1 else 0.5)
        code_bonus = 0.3 if "```" in s else 0.0
        q_bonus    = 0.1 if "?" in s else 0.0
        return kw_score + pos_score + code_bonus + q_bonus

    scored = sorted(
        ((idx, s, _sentence_score(idx, s)) for idx, s in enumerate(sentences)),
        key=lambda x: x[2],
        reverse=True,
    )

    selected: set[int] = set()
    total = 0
    for idx, s, _ in scored:
        if total + len(s) + 1 <= max_chars:
            selected.add(idx)
            total += len(s) + 1
        if total >= max_chars:
            break

    if not selected:
        # Fallback: the single highest-scoring sentence, truncated at a word
        # boundary to avoid cutting mid-word.
        best = scored[0][1][:max_chars] if scored else text[:max_chars]
        last_space = best.rfind(" ")
        return best[:last_space] if last_space > 0 else best

    return " ".join(sentences[i] for i in sorted(selected))


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
    _KEYWORDS = _IMPORTANCE_KEYWORDS
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


def _score_relevance(query: str, text: str) -> float:
    """
    Keyword-overlap relevance score between *query* and a memory *text*.

    Returns a float in [0.0, 1.0] where 1.0 means every meaningful query
    word appears in the text.  Common stopwords are ignored so that short
    but precise queries ("user's name?") are scored faithfully.

    This is intentionally lightweight (no embeddings, no ML) so it adds
    zero latency to the deliberation cycle.  For the Bedrock tier – which
    typically contains O(100) short facts – linear scanning is negligible.
    """
    _STOPWORDS: frozenset[str] = frozenset({
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
        "to", "of", "and", "or", "in", "for", "with", "that", "this",
        "at", "by", "from", "on", "as", "but", "not", "what", "how",
        "do", "does", "did", "can", "could", "will", "would", "should",
    })
    if not query or not text:
        return 0.0

    def _words(s: str) -> set[str]:
        return {w.lower().strip(".,!?;:\"'()[]{}") for w in s.split()} - _STOPWORDS

    q_words = _words(query)
    if not q_words:
        return 0.0
    t_words = _words(text)
    return len(q_words & t_words) / len(q_words)
