"""
Agentic - Memory View
======================
Browse the Memory Lattice: Crystal (episodic) and Bedrock (facts).
Read-only panel – writes happen via the model or Memory Ops skills.
"""
from __future__ import annotations

import tkinter as tk
from typing import Any

from core.memory_lattice import MemoryLattice
from ui.components import AgButton, AgFrame, AgLabel, ScrolledText
from ui.theme import FONTS, M, Palette


class MemoryView(tk.Frame):
    def __init__(
        self, master: Any, pal: Palette, get_memory: Any
    ) -> None:
        super().__init__(master, bg=pal.bg_base)
        self._pal = pal
        self._get_memory = get_memory
        self._build_ui()

    def _build_ui(self) -> None:
        pal = self._pal
        pad = M.padding_md

        hdr = AgFrame(self, pal)
        hdr.pack(fill="x", padx=pad, pady=(pad, M.padding_sm))
        AgLabel(hdr, pal, text="Memory Lattice", bold=True, size=FONTS.size_h2).pack(side="left")
        AgButton(hdr, pal, text="⟳ Refresh", command=self._refresh, kind="ghost").pack(side="right")

        # Tabs row
        tabs = AgFrame(self, pal)
        tabs.pack(fill="x", padx=pad, pady=(0, M.padding_sm))
        self._tab_var = tk.StringVar(value="fluid")
        for label, val in (
            ("Session (Fluid)", "fluid"),
            ("Long-Term Facts (Bedrock)", "bedrock"),
            ("Episode Log (Crystal)", "crystal"),
        ):
            tk.Radiobutton(
                tabs,
                text=label, value=val,
                variable=self._tab_var,
                bg=pal.bg_base, fg=pal.fg_primary,
                activebackground=pal.bg_hover,
                activeforeground=pal.accent,
                selectcolor=pal.bg_raised,
                command=self._refresh,
            ).pack(side="left", padx=(0, pad))

        # Content
        self._display = ScrolledText(self, pal)
        self._display.pack(fill="both", expand=True, padx=pad, pady=(0, pad))

        self._refresh()

    def _refresh(self) -> None:
        mem: MemoryLattice | None = self._get_memory()
        if mem is None:
            self._display.clear()
            self._display.append("No active session.\n", tag="dim")
            return

        tab = self._tab_var.get()
        self._display.clear()

        if tab == "fluid":
            entries = mem.fluid_read()
            if not entries:
                self._display.append("No session messages yet.\n", tag="dim")
            else:
                import time
                for e in entries:
                    ts = time.strftime("%H:%M:%S", time.localtime(e.ts))
                    self._display.append(f"[{ts}] {e.role.upper()}\n", tag="info")
                    self._display.append(e.text + "\n")
                    if e.tags:
                        self._display.append(f"tags: {', '.join(e.tags)}\n", tag="dim")
                    self._display.append("\n")
        elif tab == "bedrock":
            facts = mem.bedrock_query(limit=50)
            if not facts:
                self._display.append("No facts stored yet.\n", tag="dim")
            else:
                for f in facts:
                    self._display.append(f"[{f.category}]  ", tag="user")
                    self._display.append(f"{f.text}\n")
                    self._display.append(
                        f"  confidence: {f.confidence:.2f}\n", tag="dim"
                    )
        else:
            records = mem.crystal_query(limit=30)
            if not records:
                self._display.append("No episodic records yet.\n", tag="dim")
            else:
                import time
                for r in sorted(records, key=lambda x: x.ts):
                    ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(r.ts))
                    self._display.append(f"─── {ts} ───\n", tag="info")
                    self._display.append(r.summary + "\n")
                    if r.tags:
                        self._display.append(
                            f"tags: {', '.join(r.tags)}\n", tag="dim"
                        )
