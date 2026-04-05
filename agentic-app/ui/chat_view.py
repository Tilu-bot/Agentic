"""
Agentic - Chat View
====================
The primary chat interface panel.

Features:
  • Streaming token display (tokens injected via thread-safe queue)
  • Role-tagged message bubbles (user / assistant / system / skill)
  • "New session" button
  • Token counter in the status bar
  • Scroll-to-bottom on new content
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from typing import Any, Callable

from ui.components import AgButton, AgFrame, AgLabel, ScrolledText
from ui.theme import FONTS, M, Palette


class ChatView(tk.Frame):
    """
    Chat panel: occupies the centre of the main window.
    Tokens are delivered via _token_queue so this widget remains
    in the main thread while the Cortex runs in a background thread.
    """

    def __init__(
        self,
        master: Any,
        pal: Palette,
        on_submit: Callable[[str], None],
        on_new_session: Callable[[], None],
    ) -> None:
        super().__init__(master, bg=pal.bg_base)
        self._pal = pal
        self._on_submit = on_submit
        self._on_new_session = on_new_session
        self._token_queue: queue.Queue[str | None] = queue.Queue()
        self._streaming = False
        self._token_count = 0
        self._is_first_token = True

        self._build_ui()
        self._poll_token_queue()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pal = self._pal

        # Top bar
        top = AgFrame(self, pal)
        top.pack(fill="x", side="top", padx=M.padding_md, pady=(M.padding_sm, 0))

        AgLabel(top, pal, text="Agentic Chat", bold=True, size=FONTS.size_lg).pack(side="left")

        AgButton(
            top, pal, text="+ New Chat",
            command=self._on_new_session,
            kind="ghost",
        ).pack(side="right")

        # Divider
        div = tk.Frame(self, bg=pal.border, height=1)
        div.pack(fill="x", padx=0, pady=(M.padding_sm, 0))

        # Message display
        self._display = ScrolledText(self, pal)
        self._display.pack(fill="both", expand=True, padx=M.padding_sm, pady=M.padding_sm)

        # Status row
        status_row = AgFrame(self, pal)
        status_row.pack(fill="x", padx=M.padding_md, pady=(0, M.padding_xs))
        self._status_lbl = AgLabel(status_row, pal, text="Ready", muted=True, size=FONTS.size_xs)
        self._status_lbl.pack(side="left")
        self._token_lbl = AgLabel(
            status_row, pal, text="0 tokens", muted=True, size=FONTS.size_xs,
            bg=pal.bg_base,
        )
        self._token_lbl.pack(side="right")

        # Bottom input bar
        bottom = AgFrame(self, pal, raised=True)
        bottom.pack(fill="x", side="bottom", padx=M.padding_sm, pady=M.padding_sm)

        self._input = tk.Text(
            bottom,
            bg=pal.bg_input,
            fg=pal.fg_primary,
            insertbackground=pal.accent,
            selectbackground=pal.accent_dim,
            selectforeground=pal.fg_primary,
            relief="flat",
            wrap="word",
            height=3,
            font=(FONTS.family_ui, FONTS.size_md),
            padx=M.padding_sm,
            pady=M.padding_sm,
        )
        self._input.pack(fill="x", side="left", expand=True, padx=(0, M.padding_sm))

        self._send_btn = AgButton(
            bottom, pal, text="Send ↵",
            command=self._submit,
            kind="primary",
        )
        self._send_btn.pack(side="right", fill="y")

        # Keyboard shortcut: Enter submits; Shift+Enter adds newline
        self._input.bind("<Return>",       self._on_return)
        self._input.bind("<Shift-Return>", lambda e: None)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _on_return(self, event: Any) -> str:
        self._submit()
        return "break"   # prevent default newline insertion

    def _submit(self) -> None:
        text = self._input.get("1.0", "end-1c").strip()
        if not text or self._streaming:
            return
        self._input.delete("1.0", "end")
        self._show_user_message(text)
        self._set_status("Thinking…", busy=True)
        self._streaming = True
        self._is_first_token = True
        self._on_submit(text)

    # ------------------------------------------------------------------
    # Message rendering
    # ------------------------------------------------------------------

    def _show_user_message(self, text: str) -> None:
        self._display.append("\n")
        self._display.append("You\n", tag="user")
        self._display.append(text + "\n")

    def _begin_assistant_message(self) -> None:
        self._display.append("\n")
        self._display.append("Agentic\n", tag="user")

    def append_system(self, text: str) -> None:
        self._display.append(f"\n[System] {text}\n", tag="system")

    def append_info(self, text: str) -> None:
        self._display.append(f"\n{text}\n", tag="info")

    def clear(self) -> None:
        self._display.clear()
        self._token_count = 0
        self._update_token_counter()

    # ------------------------------------------------------------------
    # Streaming token delivery (thread-safe)
    # ------------------------------------------------------------------

    def push_token(self, token: str) -> None:
        """Called from any thread; delivers a token to the display queue."""
        self._token_queue.put(token)

    def finish_streaming(self) -> None:
        """Signal that the current response is complete."""
        self._token_queue.put(None)   # sentinel

    def _poll_token_queue(self) -> None:
        """Drains the token queue from the main thread via after()."""
        try:
            for _ in range(80):    # drain up to 80 tokens per poll cycle
                token = self._token_queue.get_nowait()
                if token is None:
                    self._streaming = False
                    self._set_status("Ready")
                    self._display.append("\n")
                    break
                if self._is_first_token:
                    self._begin_assistant_message()
                    self._is_first_token = False
                self._display.append(token)
                self._token_count += 1
                self._update_token_counter()
        except queue.Empty:
            pass
        self.after(30, self._poll_token_queue)

    def _update_token_counter(self) -> None:
        self._token_lbl.config(text=f"{self._token_count} tokens")

    def _set_status(self, text: str, busy: bool = False) -> None:
        colour = self._pal.warn if busy else self._pal.fg_muted
        self._status_lbl.config(text=text, fg=colour)
        self._send_btn.config(state="disabled" if busy else "normal")
