"""
Agentic - Task Panel
=====================
Shows real-time status of all active TaskFibers.
Updates via Signal Lattice subscriptions so it requires no polling.
"""
from __future__ import annotations

import time
import tkinter as tk
from typing import Any

from core.signal_lattice import SigKind, Signal, lattice
from ui.components import AgFrame, AgLabel, AgProgressBar
from ui.theme import FONTS, M, Palette


class FiberCard(tk.Frame):
    """One card per active TaskFiber."""

    def __init__(self, master: Any, pal: Palette, fiber_id: str, label: str) -> None:
        super().__init__(
            master, bg=pal.bg_raised, padx=M.padding_sm, pady=M.padding_sm,
        )
        self._pal = pal
        self.fiber_id = fiber_id
        self._born = time.monotonic()

        # Label row
        hdr = AgFrame(self, pal, raised=True)
        hdr.pack(fill="x")
        AgLabel(hdr, pal, text=label[:60], bold=True, size=FONTS.size_sm, bg=pal.bg_raised).pack(side="left")
        self._status_lbl = AgLabel(
            hdr, pal, text="running", muted=True, size=FONTS.size_xs, bg=pal.bg_raised
        )
        self._status_lbl.pack(side="right")

        # Progress bar
        self._bar = AgProgressBar(self, pal, height=4)
        self._bar.pack(fill="x", pady=(M.padding_xs, 0))

        # Time label
        self._time_lbl = AgLabel(
            self, pal, text="0.0s", muted=True, size=FONTS.size_xs, bg=pal.bg_raised
        )
        self._time_lbl.pack(anchor="e")

        self._tick()

    def set_progress(self, value: float) -> None:
        self._bar.set_value(value)

    def set_status(self, status: str, colour: str | None = None) -> None:
        self._status_lbl.config(
            text=status, fg=colour or self._pal.fg_muted
        )

    def _tick(self) -> None:
        elapsed = time.monotonic() - self._born
        self._time_lbl.config(text=f"{elapsed:.1f}s")
        self.after(500, self._tick)


class TaskPanel(tk.Frame):
    """
    Side panel showing active Task Fibers.
    Subscribes to TASK_* signals from the Signal Lattice.
    Must be created in the main (UI) thread.
    """

    def __init__(self, master: Any, pal: Palette) -> None:
        super().__init__(master, bg=pal.bg_base)
        self._pal = pal
        self._cards: dict[str, FiberCard] = {}
        self._build_ui()
        self._subscribe()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pal = self._pal

        AgLabel(
            self, pal, text="Activity",
            bold=True, size=FONTS.size_sm,
            bg=pal.bg_base,
        ).pack(fill="x", padx=M.padding_sm, pady=(M.padding_sm, M.padding_xs))

        div = tk.Frame(self, bg=pal.border, height=1)
        div.pack(fill="x", pady=(0, M.padding_xs))

        self._canvas = tk.Canvas(self, bg=pal.bg_base, highlightthickness=0)
        sb = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.config(yscrollcommand=sb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._inner = AgFrame(self._canvas, pal)
        self._canvas_win = self._canvas.create_window(
            (0, 0), window=self._inner, anchor="nw"
        )
        self._inner.bind("<Configure>", self._on_inner_resize)
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        # Activity feed below task cards keeps the panel informative even when
        # no long-running fibers are active.
        self._activity = tk.Text(
            self,
            height=12,
            bg=pal.bg_raised,
            fg=pal.fg_muted,
            relief="flat",
            wrap="word",
            state="disabled",
            font=(FONTS.family_code, FONTS.size_xs),
            padx=M.padding_sm,
            pady=M.padding_sm,
        )
        self._activity.pack(fill="x", padx=M.padding_sm, pady=(M.padding_xs, M.padding_sm))

    def _on_inner_resize(self, _: Any) -> None:
        self._canvas.config(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, evt: Any) -> None:
        self._canvas.itemconfig(self._canvas_win, width=evt.width)

    # ------------------------------------------------------------------
    # Signal subscriptions (called from any thread → use after() for UI)
    # ------------------------------------------------------------------

    def _subscribe(self) -> None:
        lattice.on(SigKind.TASK_SPAWNED,   self._handle_spawned)
        lattice.on(SigKind.TASK_PROGRESS,  self._handle_progress)
        lattice.on(SigKind.TASK_COMPLETED, self._handle_completed)
        lattice.on(SigKind.TASK_FAILED,    self._handle_failed)
        lattice.on(SigKind.TASK_CANCELLED, self._handle_cancelled)
        lattice.on(SigKind.DELIBERATION_START, self._handle_deliberation_start)
        lattice.on(SigKind.REACT_ITERATION, self._handle_react_iteration)
        lattice.on(SigKind.SKILL_INVOKED, self._handle_skill_invoked)
        lattice.on(SigKind.SKILL_RESULT, self._handle_skill_result)
        lattice.on(SigKind.SKILL_ERROR, self._handle_skill_error)
        lattice.on(SigKind.MODEL_LOADING, self._handle_model_loading)

    def _handle_deliberation_start(self, sig: Signal) -> None:
        self.after(0, self._append_activity, "Reasoning started")

    def _handle_react_iteration(self, sig: Signal) -> None:
        i = sig.payload.get("iteration", "?")
        tools = ", ".join(sig.payload.get("skills_run", [])) or "none"
        self.after(0, self._append_activity, f"Iteration {i}: tools {tools}")

    def _handle_skill_invoked(self, sig: Signal) -> None:
        skill = sig.payload.get("skill", "unknown")
        self.after(0, self._append_activity, f"Skill invoked: {skill}")

    def _handle_skill_result(self, sig: Signal) -> None:
        skill = sig.payload.get("skill", "unknown")
        self.after(0, self._append_activity, f"Skill done: {skill}")

    def _handle_skill_error(self, sig: Signal) -> None:
        skill = sig.payload.get("skill", "unknown")
        err = str(sig.payload.get("error", ""))[:80]
        self.after(0, self._append_activity, f"Skill error: {skill} ({err})")

    def _handle_model_loading(self, sig: Signal) -> None:
        stage = str(sig.payload.get("stage", ""))
        if stage in ("start", "download_start", "tokenizer", "weights", "done", "error"):
            self.after(0, self._append_activity, f"Model stage: {stage}")

    def _handle_spawned(self, sig: Signal) -> None:
        fid   = sig.payload["fiber_id"]
        label = sig.payload["label"]
        self.after(0, self._add_card, fid, label)

    def _handle_progress(self, sig: Signal) -> None:
        fid  = sig.payload["fiber_id"]
        prog = sig.payload["progress"]
        self.after(0, self._update_progress, fid, prog)

    def _handle_completed(self, sig: Signal) -> None:
        fid = sig.payload["fiber_id"]
        self.after(0, self._mark_done, fid)

    def _handle_failed(self, sig: Signal) -> None:
        fid = sig.payload["fiber_id"]
        err = sig.payload.get("error", "")
        self.after(0, self._mark_failed, fid, err)

    def _handle_cancelled(self, sig: Signal) -> None:
        fid = sig.payload["fiber_id"]
        self.after(0, self._mark_cancelled, fid)

    # ------------------------------------------------------------------
    # Card management (main thread only)
    # ------------------------------------------------------------------

    def _add_card(self, fiber_id: str, label: str) -> None:
        card = FiberCard(self._inner, self._pal, fiber_id, label)
        card.pack(fill="x", padx=M.padding_xs, pady=M.padding_xs)
        self._cards[fiber_id] = card

    def _update_progress(self, fiber_id: str, progress: float) -> None:
        card = self._cards.get(fiber_id)
        if card:
            card.set_progress(progress)

    def _mark_done(self, fiber_id: str) -> None:
        card = self._cards.get(fiber_id)
        if card:
            card.set_status("✓ done", self._pal.ok)
            card.set_progress(1.0)
            self.after(4000, lambda: self._remove_card(fiber_id))

    def _mark_failed(self, fiber_id: str, error: str) -> None:
        card = self._cards.get(fiber_id)
        if card:
            card.set_status(f"✗ failed: {error[:40]}", self._pal.danger)

    def _mark_cancelled(self, fiber_id: str) -> None:
        card = self._cards.get(fiber_id)
        if card:
            card.set_status("cancelled", self._pal.fg_dim)
            self.after(3000, lambda: self._remove_card(fiber_id))

    def _remove_card(self, fiber_id: str) -> None:
        card = self._cards.pop(fiber_id, None)
        if card:
            card.destroy()

    def _append_activity(self, text: str) -> None:
        ts = time.strftime("%H:%M:%S")
        self._activity.config(state="normal")
        self._activity.insert("end", f"[{ts}] {text}\n")
        # Keep the feed bounded.
        lines = int(self._activity.index("end-1c").split(".")[0])
        if lines > 200:
            self._activity.delete("1.0", "40.0")
        self._activity.see("end")
        self._activity.config(state="disabled")
