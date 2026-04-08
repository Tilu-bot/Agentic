"""
Agentic - Chat View
====================
The primary chat interface panel.

Features:
  • Rich message display with avatars and timestamps
  • Streaming token display (tokens injected via thread-safe queue)
  • Role-tagged message bubbles (user / assistant / system / skill)
  • Suggested actions for quick prompts (like Gemini)
  • Typing indicator with animation
  • Message action buttons (copy, regenerate, delete)
  • "New session" button
  • Token counter in the status bar
  • Scroll-to-bottom on new content
"""
from __future__ import annotations

import queue
import time
import tkinter as tk
from datetime import datetime
from typing import Any, Callable

from ui.components import (
    AgButton, AgLabel, ScrolledText, TypingIndicator
)
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
        self._assistant_buffer: list[str] = []
        self._assistant_content_start: str | None = None
        self._has_messages = False
        self._model_hint = "model: loading"
        self._tools_hint = "tools: 0"
        self._placeholder = "Message..."
        self._placeholder_visible = False
        self._footer_text = "AI generated responses can have errors, human oversight is needed."
        self._prompt_history: list[str] = []
        self._history_index: int | None = None
        self._thinking_after_job: str | None = None
        self._request_started_at: float | None = None

        self._build_ui()
        self._poll_token_queue()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pal = self._pal

        # Configure grid layout for ChatView
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Top bar (clean chat header)
        top = tk.Frame(self, bg=pal.bg_base, height=84)
        top.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        top.grid_propagate(False)

        top_inner = tk.Frame(top, bg=pal.bg_base)
        top_inner.pack(fill="both", expand=True, padx=M.padding_lg, pady=M.padding_md)
        top_inner.grid_columnconfigure(0, weight=1)

        title_wrap = tk.Frame(top_inner, bg=pal.bg_base)
        title_wrap.grid(row=0, column=0, sticky="w")
        tk.Label(
            title_wrap,
            text="Messages",
            bg=pal.bg_base,
            fg=pal.fg_primary,
            font=(FONTS.family_ui, FONTS.size_xl, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            title_wrap,
            text="Ask anything and get instant replies.",
            bg=pal.bg_base,
            fg=pal.fg_muted,
            font=(FONTS.family_ui, FONTS.size_sm),
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        actions_wrap = tk.Frame(top_inner, bg=pal.bg_base)
        actions_wrap.grid(row=0, column=1, sticky="e")

        AgButton(
            actions_wrap,
            pal,
            text="New Chat",
            command=self._on_new_session,
            kind="secondary",
            icon="new",
            icon_size=16,
        ).pack(side="left", padx=(0, M.padding_sm))

        tk.Button(
            actions_wrap,
            text="⚙",
            command=lambda: None,
            bg=pal.bg_base,
            fg=pal.fg_muted,
            activebackground=pal.bg_hover,
            activeforeground=pal.fg_primary,
            relief="flat",
            bd=0,
            padx=M.padding_sm,
            pady=M.padding_sm,
            cursor="hand2",
            font=(FONTS.family_ui, FONTS.size_md),
        ).pack(side="left")

        # Top border
        border_top = tk.Frame(self, bg=pal.border, height=2)
        border_top.grid(row=1, column=0, sticky="ew")

        # Main body content area
        content = tk.Frame(self, bg=pal.bg_base)
        content.grid(row=2, column=0, sticky="nsew", padx=M.padding_lg, pady=M.padding_lg)
        content.grid_rowconfigure(1, weight=1)
        content.grid_columnconfigure(0, weight=1)

        # Hero section (small empty-state hint; hidden after first message)
        self._hero_container = tk.Frame(content, bg=pal.bg_base)
        self._hero_container.grid(row=0, column=0, sticky="ew", padx=0, pady=(M.padding_sm, M.padding_md))
        self._hero_container.grid_columnconfigure(0, weight=1)

        self._hero_sub = tk.Label(
            self._hero_container,
            text="Clear sender bubbles. Clear AI replies.",
            bg=pal.bg_base,
            fg=pal.fg_muted,
            font=(FONTS.family_ui, FONTS.size_sm),
        )
        self._hero_sub.grid(row=0, column=0, sticky="w")

        # Message display area with clean border
        display_shell = tk.Frame(
            content,
            bg=pal.bg_raised,
            highlightthickness=1,
            highlightbackground=pal.border_dim,
            bd=0,
            padx=0,
            pady=0,
        )
        display_shell.grid(row=1, column=0, sticky="nsew", pady=(0, M.padding_lg))
        display_shell.grid_rowconfigure(0, weight=1)
        display_shell.grid_columnconfigure(0, weight=1)

        self._display = ScrolledText(display_shell, pal, bg=pal.bg_raised)
        self._display.grid(row=0, column=0, sticky="nsew")

        # Typing indicator (hidden by default)
        self._typing = TypingIndicator(content, pal)
        self._typing.grid(row=2, column=0, sticky="w", padx=M.padding_sm, pady=(0, M.padding_md))
        self._typing.grid_remove()

        # Composer (Instagram-like message box)
        composer_shell = tk.Frame(
            content,
            bg=pal.bg_raised,
            highlightthickness=1,
            highlightbackground=pal.border_dim,
            bd=0,
            padx=M.padding_md,
            pady=M.padding_md,
        )
        composer_shell.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=0,
            pady=(M.padding_lg, 0),
        )
        composer_shell.grid_columnconfigure(0, weight=1)

        self._input = tk.Entry(
            composer_shell,
            bg=pal.bg_raised,
            fg=pal.fg_primary,
            insertbackground=pal.fg_primary,
            selectbackground=pal.accent_dim,
            selectforeground=pal.fg_primary,
            relief="flat",
            highlightthickness=0,
            borderwidth=0,
            font=(FONTS.family_ui, FONTS.size_lg),
        )
        self._input.grid(row=0, column=0, sticky="ew", padx=(0, M.padding_sm), ipady=10)

        self._send_btn = tk.Button(
            composer_shell,
            text="➤",
            command=self._submit,
            bg="#0095f6",
            fg="#ffffff",
            activebackground="#0077c2",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=M.padding_sm,
            pady=M.padding_sm,
            cursor="hand2",
            font=(FONTS.family_ui, FONTS.size_md, "bold"),
            width=2,
        )
        self._send_btn.grid(row=0, column=1, padx=(M.padding_sm, 0), pady=0, sticky="e")

        self._status_lbl = AgLabel(content, pal, text=self._footer_text, muted=True, size=FONTS.size_xs, bg=pal.bg_base)
        self._status_lbl.grid(row=4, column=0, sticky="w", pady=(M.padding_sm, 0))

        # Keyboard shortcut: Enter submits.
        self._input.bind("<Return>", self._on_return)
        self._input.bind("<Up>", self._on_history_up)
        self._input.bind("<Down>", self._on_history_down)
        self._input.bind("<FocusIn>", self._on_focus_in)
        self._input.bind("<FocusOut>", self._on_focus_out)
        self._show_placeholder()

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _on_return(self, event: Any) -> str:
        self._submit()
        return "break"   # prevent default newline insertion

    def _submit(self) -> None:
        if self._placeholder_visible:
            text = ""
        else:
            text = self._input.get().strip()
        if not text or self._streaming:
            return
        self._prompt_history.append(text)
        self._history_index = None
        self._input.delete(0, "end")
        self._show_placeholder()
        self._show_user_message(text)
        self._set_status("Working...", busy=True)
        self._schedule_thinking_indicator()
        self._request_started_at = time.time()
        self._streaming = True
        self._is_first_token = True
        self._on_submit(text)

    def _submit_shortcut(self, text: str) -> None:
        if self._streaming:
            return
        self._prompt_history.append(text)
        self._history_index = None
        self._show_user_message(text)
        self._set_status("Working...", busy=True)
        self._schedule_thinking_indicator()
        self._request_started_at = time.time()
        self._streaming = True
        self._is_first_token = True
        self._on_submit(text)

    def _schedule_thinking_indicator(self) -> None:
        self._cancel_thinking_indicator()
        self._thinking_after_job = self.after(700, self._show_thinking_if_still_waiting)

    def _cancel_thinking_indicator(self) -> None:
        if self._thinking_after_job is None:
            return
        try:
            self.after_cancel(self._thinking_after_job)
        except tk.TclError:
            pass
        self._thinking_after_job = None

    def _show_thinking_if_still_waiting(self) -> None:
        self._thinking_after_job = None
        if self._streaming and self._is_first_token:
            self._typing.grid()
            self._typing.start()

    def _on_history_up(self, _: Any) -> str:
        if self._streaming or not self._prompt_history:
            return "break"
        if self._history_index is None:
            self._history_index = len(self._prompt_history) - 1
        else:
            self._history_index = max(0, self._history_index - 1)
        self._hide_placeholder()
        self._input.delete(0, "end")
        self._input.insert(0, self._prompt_history[self._history_index])
        return "break"

    def _on_history_down(self, _: Any) -> str:
        if self._streaming or not self._prompt_history:
            return "break"
        if self._history_index is None:
            return "break"
        next_index = self._history_index + 1
        if next_index >= len(self._prompt_history):
            self._history_index = None
            self._show_placeholder()
            return "break"
        self._history_index = next_index
        self._hide_placeholder()
        self._input.delete(0, "end")
        self._input.insert(0, self._prompt_history[self._history_index])
        return "break"

    # ------------------------------------------------------------------
    # Message rendering
    # ------------------------------------------------------------------

    def _show_user_message(self, text: str) -> None:
        self._hide_hero()
        self._display.append("\n", tag="dim")
        self._display.append(text + "\n", tag="user_bubble")
        now = datetime.now().strftime("%H:%M")
        self._display.append(f"{now}\n", tag="timestamp_user")
        self._display.append("\n", tag="dim")

    def _begin_assistant_message(self) -> None:
        self._hide_hero()
        self._display.append("\n", tag="dim")
        elapsed = 1
        if self._request_started_at is not None:
            elapsed = max(1, int(round(time.time() - self._request_started_at)))
        self._display.append(f"Thought for {elapsed}s  ›\n", tag="reasoning")
        self._assistant_content_start = self._display.get_end_index()
        self._assistant_buffer = []

    def append_system(self, text: str) -> None:
        self._display.append(f"\n[System] {text}\n", tag="system")

    def append_info(self, text: str) -> None:
        self._display.append(f"\n{text}\n", tag="info")

    def clear(self) -> None:
        self._display.clear()
        self._token_count = 0
        self._update_token_counter()
        self._has_messages = False
        self._show_hero()
        self._show_placeholder()
        self._typing.stop()

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
                    self._cancel_thinking_indicator()
                    self._typing.stop()
                    self._typing.grid_remove()
                    self._set_status("Ready")
                    if self._assistant_content_start is not None and self._assistant_buffer:
                        end_index = self._display.get_end_index()
                        rendered = "".join(self._assistant_buffer)
                        self._display.replace_range_with_markdown(
                            self._assistant_content_start,
                            end_index,
                            rendered,
                            base_tag="assistant_bubble",
                        )
                        now = datetime.now().strftime("%H:%M")
                        self._display.append(f"\n{now}\n", tag="timestamp")
                    self._assistant_content_start = None
                    self._assistant_buffer = []
                    self._request_started_at = None
                    self._display.append("\n", tag="dim")
                    break
                if self._is_first_token:
                    self._cancel_thinking_indicator()
                    self._begin_assistant_message()
                    self._is_first_token = False
                    self._typing.stop()
                    self._typing.grid_remove()
                self._display.append(token, tag="assistant_bubble")
                self._assistant_buffer.append(token)
                self._token_count += 1
                self._update_token_counter()
                self._has_messages = True
        except queue.Empty:
            pass
        except tk.TclError:
            return
        try:
            self.after(30, self._poll_token_queue)
        except tk.TclError:
            return

    def _update_token_counter(self) -> None:
        return

    def set_status(self, text: str, busy: bool = False) -> None:
        """Public proxy for status updates called from the app layer."""
        self._set_status(text, busy=busy)

    def set_runtime_info(self, model_id: str, tools_count: int) -> None:
        """Retain runtime info for future use without cluttering the UI."""
        self._model_hint = model_id
        self._tools_hint = str(tools_count)

    def _set_status(self, text: str, busy: bool = False) -> None:
        colour = self._pal.warn if busy else self._pal.fg_muted
        self._status_lbl.config(text=text if busy else self._footer_text, fg=colour)
        self._send_btn.config(state="disabled" if busy else "normal")
        self._input.config(state="disabled" if busy else "normal")
        if not busy and self._placeholder_visible:
            self._input.config(fg=self._pal.fg_dim)

    def _show_placeholder(self) -> None:
        self._input.config(state="normal")
        self._input.delete(0, "end")
        self._input.insert(0, self._placeholder)
        self._input.config(fg=self._pal.fg_dim)
        self._placeholder_visible = True

    def _hide_placeholder(self) -> None:
        if not self._placeholder_visible:
            return
        self._input.delete(0, "end")
        self._input.config(fg=self._pal.fg_primary)
        self._placeholder_visible = False

    def _on_focus_in(self, _: Any) -> None:
        if self._placeholder_visible:
            self._hide_placeholder()

    def _on_focus_out(self, _: Any) -> None:
        if self._streaming:
            return
        text = self._input.get().strip()
        if not text:
            self._show_placeholder()

    def _hide_hero(self) -> None:
        if self._has_messages:
            return
        self._has_messages = True
        try:
            self._hero_container.grid_remove()
        except tk.TclError:
            pass

    def _show_hero(self) -> None:
        try:
            self._hero_container.grid()
        except tk.TclError:
            pass
