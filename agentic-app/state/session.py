"""
Agentic - Session Manager
==========================
Manages the lifecycle of a user session: creates new sessions,
loads existing ones, and exposes the active MemoryLattice.
"""
from __future__ import annotations

import uuid
import time
from pathlib import Path

from core.memory_lattice import MemoryLattice
from state.store import Store
from utils.config import cfg
from utils.logger import build_logger

log = build_logger("agentic.session")


class SessionManager:
    def __init__(self, store: Store) -> None:
        self._store = store
        self._active_id: str = ""
        self._memory: MemoryLattice | None = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def new_session(self, title: str = "New Chat") -> str:
        sid = uuid.uuid4().hex
        self._store.session_create(sid, title=title)
        self._active_id = sid
        self._memory = MemoryLattice(
            store=self._store,
            session_id=sid,
            fluid_limit=cfg.get("working_memory_limit", 20),
        )
        log.info("New session: %s", sid)
        return sid

    def load_session(self, session_id: str) -> bool:
        sessions = {s["id"]: s for s in self._store.session_list()}
        if session_id not in sessions:
            log.warning("Session not found: %s", session_id)
            return False
        self._active_id = session_id
        self._memory = MemoryLattice(
            store=self._store,
            session_id=session_id,
            fluid_limit=cfg.get("working_memory_limit", 20),
        )
        log.info("Session loaded: %s", session_id)
        return True

    def list_sessions(self) -> list[dict]:
        return self._store.session_list()

    def load_most_recent_session(self) -> str | None:
        """Load the most recently updated session, if one exists."""
        sessions = self._store.session_list(limit=1)
        if not sessions:
            return None
        session_id = sessions[0].get("id", "")
        if not session_id:
            return None
        if self.load_session(session_id):
            return session_id
        return None

    def delete_session(self, session_id: str) -> None:
        self._store.session_delete(session_id)
        if self._active_id == session_id:
            self._active_id = ""
            self._memory = None

    def rename_session(self, session_id: str, title: str) -> None:
        self._store.session_update_title(session_id, title)

    # ------------------------------------------------------------------
    # Active session helpers
    # ------------------------------------------------------------------

    @property
    def active_id(self) -> str:
        return self._active_id

    @property
    def memory(self) -> MemoryLattice:
        if self._memory is None:
            self.new_session()
        assert self._memory is not None
        return self._memory

    def ensure_active(self) -> str:
        if not self._active_id:
            self.new_session()
        return self._active_id
