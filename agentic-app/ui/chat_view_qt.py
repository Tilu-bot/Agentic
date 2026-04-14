"""
Agentic - Chat View (PyQt6 + WebEngine)
========================================
Primary chat panel: a QWebEngineView renders the conversation thread
using HTML/CSS/JS (see chat_web.html).  Tokens are batched from a buffer
and injected into the page with runJavaScript(), which is called on the
main thread via a QTimer.

Layout
------
  ┌────────────────────────────────────────────┐
  │  Page header (title + New Chat button)     │  ← top bar
  ├────────────────────────────────────────────┤
  │  QWebEngineView                            │  ← chat thread (expands)
  ├────────────────────────────────────────────┤
  │  Composer  [input …………………………]  [Send ➤]  │  ← composer
  │  Status label                              │
  └────────────────────────────────────────────┘
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QTimer, Qt, QUrl, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QFileDialog,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

def _resolve_ui_asset(filename: str) -> Path:
    local_path = Path(__file__).parent / filename
    if local_path.exists():
        return local_path

    for root in (Path.cwd(), *Path.cwd().parents):
        for candidate_dir in (
            root / "ui",
            root / "agentic-app" / "ui",
        ):
            candidate = candidate_dir / filename
            if candidate.exists():
                return candidate

    return local_path


_HTML_PATH = _resolve_ui_asset("chat_web.html")


class ChatViewQt(QWidget):
    """
    Chat panel widget.

    Signals
    -------
    message_submitted(str)   – emitted when the user sends a message
    new_session_requested()  – emitted when "New Chat" is clicked
    suggestion_clicked(str)  – emitted when a welcome-screen chip is clicked
    """

    message_submitted:     pyqtSignal = pyqtSignal(str, list)
    stop_requested:        pyqtSignal = pyqtSignal()
    new_session_requested: pyqtSignal = pyqtSignal()
    suggestion_clicked:    pyqtSignal = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._token_buffer:  list[str] = []
        self._streaming      = False
        self._bubble_open    = False
        self._page_ready     = False
        self._pending_calls: list[str] = []   # JS calls queued before page load
        self._history:       list[str] = []
        self._history_idx:   int | None = None
        self._attachments:   list[Path] = []
        self._action_mode:   str = "send"
        self._load_stage     = ""
        self._load_short     = "model"
        self._load_start_ts  = 0.0
        self._last_dl_pct    = -1
        self._load_hint_shown = False

        self._build_ui()
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(30)
        self._flush_timer.timeout.connect(self._flush_tokens)
        self._flush_timer.start()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar ──────────────────────────────────────────────────
        top_bar = QWidget(self)
        top_bar.setObjectName("TopBar")
        top_bar.setStyleSheet("background:#1a1d27; border-bottom:1px solid #252840;")
        top_bar.setFixedHeight(64)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(24, 0, 20, 0)

        title_wrap = QWidget(top_bar)
        title_wrap.setStyleSheet("background:transparent;")
        tw_layout = QVBoxLayout(title_wrap)
        tw_layout.setContentsMargins(0, 0, 0, 0)
        tw_layout.setSpacing(1)

        lbl_title = QLabel("Chat", title_wrap)
        lbl_title.setObjectName("SectionTitle")
        lbl_title.setStyleSheet("font-size:18px; font-weight:700; color:#e2e8f0; background:transparent;")

        lbl_sub = QLabel("Ask anything, powered by your local model.", title_wrap)
        lbl_sub.setObjectName("SectionSubtitle")

        tw_layout.addWidget(lbl_title)
        tw_layout.addWidget(lbl_sub)

        self._new_chat_btn = QPushButton("＋  New Chat", top_bar)
        self._new_chat_btn.setObjectName("NewChatButton")
        self._new_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_chat_btn.clicked.connect(self.new_session_requested)

        top_layout.addWidget(title_wrap, stretch=1)
        top_layout.addWidget(self._new_chat_btn)
        root.addWidget(top_bar)

        # ── WebEngine view ────────────────────────────────────────────
        self._web = QWebEngineView(self)
        self._web.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._web.loadFinished.connect(self._on_page_loaded)
        self._web.setHtml(
            _HTML_PATH.read_text(encoding="utf-8"),
            QUrl.fromLocalFile(str(_HTML_PATH.parent) + "/"),
        )
        root.addWidget(self._web, stretch=1)

        # ── Composer area ─────────────────────────────────────────────
        composer_outer = QWidget(self)
        composer_outer.setStyleSheet(
            "background:#1a1d27; border-top:1px solid #252840;"
        )
        co_layout = QVBoxLayout(composer_outer)
        co_layout.setContentsMargins(20, 12, 20, 12)
        co_layout.setSpacing(8)

        # Inner frame (the pill-shaped input area)
        composer_frame = QFrame(composer_outer)
        composer_frame.setObjectName("ComposerFrame")
        cf_layout = QHBoxLayout(composer_frame)
        cf_layout.setContentsMargins(14, 8, 8, 8)
        cf_layout.setSpacing(8)

        self._input = QPlainTextEdit(composer_frame)
        self._input.setObjectName("ComposerInput")
        self._input.setPlaceholderText("Message Agentic…  (Enter to send, Shift+Enter for new line)")
        self._input.setFixedHeight(48)
        self._input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._input.installEventFilter(self)

        self._action_btn = QPushButton("➤", composer_frame)
        self._action_btn.setObjectName("SendButton")
        self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action_btn.setFixedSize(88, 42)
        self._action_btn.clicked.connect(self._on_action_clicked)

        self._attach_btn = QPushButton("＋", composer_frame)
        self._attach_btn.setObjectName("AttachButton")
        self._attach_btn.setToolTip("Attach files")
        self._attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._attach_btn.setFixedSize(42, 42)
        self._attach_btn.clicked.connect(self._pick_attachments)

        cf_layout.addWidget(self._input)
        cf_layout.addWidget(self._attach_btn)
        cf_layout.addWidget(self._action_btn)

        self._attachment_row = QWidget(composer_outer)
        ar_layout = QHBoxLayout(self._attachment_row)
        ar_layout.setContentsMargins(4, 0, 4, 0)
        ar_layout.setSpacing(8)

        self._attachment_lbl = QLabel(self._attachment_row)
        self._attachment_lbl.setObjectName("AttachmentLabel")
        self._attachment_lbl.setWordWrap(False)

        self._clear_attachments_btn = QPushButton("Clear", self._attachment_row)
        self._clear_attachments_btn.setObjectName("ClearAttachmentsButton")
        self._clear_attachments_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_attachments_btn.clicked.connect(self._clear_attachments)

        ar_layout.addWidget(self._attachment_lbl, stretch=1)
        ar_layout.addWidget(self._clear_attachments_btn)
        self._attachment_row.setVisible(False)

        self._status_lbl = QLabel(
            "AI responses can contain errors — please verify important information.",
            composer_outer,
        )
        self._status_lbl.setObjectName("StatusLabel")
        self._status_lbl.setWordWrap(True)

        co_layout.addWidget(composer_frame)
        co_layout.addWidget(self._attachment_row)
        co_layout.addWidget(self._status_lbl)
        root.addWidget(composer_outer)

    # ------------------------------------------------------------------
    # Event filter: intercept Enter/Up/Down in the composer
    # ------------------------------------------------------------------

    def eventFilter(self, source: object, event: object) -> bool:
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent

        if source is self._input and isinstance(event, QKeyEvent):
            if event.type() == QEvent.Type.KeyPress:
                key  = event.key()
                mods = event.modifiers()
                if key == Qt.Key.Key_Return and not (mods & Qt.KeyboardModifier.ShiftModifier):
                    self._on_action_clicked()
                    return True
                if key == Qt.Key.Key_Up and not self._input.toPlainText():
                    self._history_navigate(-1)
                    return True
                if key == Qt.Key.Key_Down:
                    self._history_navigate(1)
                    return True
        return super().eventFilter(source, event)

    # ------------------------------------------------------------------
    # User interaction
    # ------------------------------------------------------------------
    def _on_action_clicked(self) -> None:
        if self._streaming:
            self._request_stop()
        else:
            self._submit()

    def _submit(self) -> None:
        if self._streaming:
            return
        text = self._input.toPlainText().strip()
        if not text and not self._attachments:
            return
        from utils.logger import build_logger
        log = build_logger("agentic.chat_view")
        if self._attachments:
            log.info(f"Submitting message with {len(self._attachments)} attachment(s)")
        prompt_text = text or "Please review the attached files and help me with them."
        bubble_text = text or "Attached files"
        attachments = [str(path) for path in self._attachments]
        self._history.append(prompt_text)
        self._history_idx = None
        self._input.clear()
        self._js(f"window.addUserMessage({json.dumps(bubble_text)})")
        self._streaming = True
        self._action_mode = "stop"
        self._refresh_action_button()
        self._attach_btn.setEnabled(False)
        self._input.setEnabled(False)
        self._set_status("Working…", busy=True)
        self._clear_attachments(preserve_ui=False)
        log.info(f"Emitting message_submitted signal with attachments: {[Path(a).name for a in attachments]}")
        self.message_submitted.emit(prompt_text, attachments)

    def submit_suggestion(self, text: str) -> None:
        """Programmatically submit a suggestion chip click."""
        if self._streaming:
            return
        attachments = [str(path) for path in self._attachments]
        self._history.append(text)
        self._history_idx = None
        self._js(f"window.addUserMessage({json.dumps(text)})")
        self._streaming = True
        self._action_mode = "stop"
        self._refresh_action_button()
        self._attach_btn.setEnabled(False)
        self._input.setEnabled(False)
        self._set_status("Working…", busy=True)
        self._clear_attachments(preserve_ui=False)
        self.message_submitted.emit(text, attachments)

    def _request_stop(self) -> None:
        if not self._streaming:
            return
        self._action_btn.setEnabled(False)
        self._set_status("Stopping…", busy=True)
        self.stop_requested.emit()

    def _pick_attachments(self) -> None:
        if self._streaming:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Attach files",
            str(Path.home()),
            "Documents (*.txt *.md *.csv *.json *.yml *.yaml *.py *.pdf *.docx *.xlsx *.pptx);;All Files (*)",
        )
        if not files:
            return
        from utils.logger import build_logger
        log = build_logger("agentic.chat_view")
        log.info(f"File dialog returned {len(files)} file(s)")
        for file_path in files:
            path = Path(file_path).expanduser().resolve()
            if not path.exists():
                log.warning(f"Selected file does not exist: {path}")
                continue
            if path not in self._attachments:
                log.info(f"Adding attachment: {path.name}")
                self._attachments.append(path)
            else:
                log.info(f"Attachment already added: {path.name}")
        log.info(f"Total attachments now: {len(self._attachments)}")
        self._refresh_attachments_ui()

    def _clear_attachments(self, preserve_ui: bool = True) -> None:
        self._attachments.clear()
        if preserve_ui:
            self._refresh_attachments_ui()

    def _refresh_attachments_ui(self) -> None:
        if not self._attachments:
            self._attachment_row.setVisible(False)
            self._attachment_lbl.clear()
            return
        names = [path.name for path in self._attachments]
        self._attachment_lbl.setText("Attached: " + ", ".join(names))
        self._attachment_row.setVisible(True)

    def _history_navigate(self, direction: int) -> None:
        if not self._history:
            return
        if self._history_idx is None:
            self._history_idx = len(self._history) - 1 if direction < 0 else 0
        else:
            self._history_idx = max(0, min(len(self._history) - 1, self._history_idx + direction))
        self._input.setPlainText(self._history[self._history_idx])

    def _refresh_action_button(self) -> None:
        if self._action_mode == "stop":
            self._action_btn.setText("Stop")
            self._action_btn.setObjectName("StopButton")
        else:
            self._action_btn.setText("➤")
            self._action_btn.setObjectName("SendButton")
        self._action_btn.setEnabled(True)
        self._action_btn.style().unpolish(self._action_btn)
        self._action_btn.style().polish(self._action_btn)

    # ------------------------------------------------------------------
    # Token streaming (called from main thread via Qt signal)
    # ------------------------------------------------------------------

    def push_token(self, token: str) -> None:
        """Buffer a streaming token (safe to call from any thread via Qt signal)."""
        if not self._streaming:
            # First token — start the assistant bubble
            self._streaming = True
        self._token_buffer.append(token)

    def finish_streaming(self) -> None:
        """Signal that the current response stream is complete."""
        self._flush_tokens(finish=True)

    def _flush_tokens(self, finish: bool = False) -> None:
        """Drain the buffer and inject tokens into the page (main thread only)."""
        if self._token_buffer:
            batch = "".join(self._token_buffer)
            self._token_buffer.clear()
            # Open the assistant bubble on the very first batch
            if not self._bubble_open:
                self._js("window.beginAssistantMessage()")
                self._bubble_open = True
            self._js(f"window.appendTokens({json.dumps(batch)})")

        if finish:
            if self._bubble_open:
                self._js("window.finishStreaming()")
                self._bubble_open = False
            self._streaming = False
            self._action_mode = "send"
            self._refresh_action_button()
            self._attach_btn.setEnabled(True)
            self._input.setEnabled(True)
            self._input.setFocus()
            self._set_status(
                "AI responses can contain errors — please verify important information."
            )

    def append_system(self, text: str) -> None:
        self._js(f"window.addSystemMessage({json.dumps(text)})")

    def append_info(self, text: str) -> None:
        self._js(f"window.addInfoMessage({json.dumps(text)})")

    def append_assistant(self, text: str) -> None:
        self._js(f"window.addAssistantMessage({json.dumps(text)})")

    def hydrate_from_fluid(self, entries: list[object]) -> None:
        """Replay persisted fluid memory entries into the chat thread."""
        if not entries:
            return
        self.clear()
        for entry in entries:
            role = str(getattr(entry, "role", "")).lower()
            text = str(getattr(entry, "text", "")).strip()
            if not text:
                continue
            if role == "user":
                self._js(f"window.addUserMessage({json.dumps(text)})")
            elif role == "assistant":
                self.append_assistant(text)
            elif role in {"system", "skill"}:
                self.append_system(text)
            else:
                self.append_info(text)

    def clear(self) -> None:
        self._js("window.clearMessages()")
        self._token_buffer.clear()
        self._bubble_open = False
        self._streaming   = False
        self._action_mode = "send"
        self._refresh_action_button()
        self._attach_btn.setEnabled(True)
        self._input.setEnabled(True)
        self._clear_attachments()
        self._set_status(
            "AI responses can contain errors — please verify important information."
        )

    def set_status(self, text: str, busy: bool = False) -> None:
        self._set_status(text, busy)

    # ------------------------------------------------------------------
    # Model loading progress
    # ------------------------------------------------------------------

    def handle_model_loading(self, payload: dict) -> None:
        stage    = payload.get("stage", "")
        model_id = payload.get("model_id", "model")
        short    = model_id.split("/")[-1] if "/" in model_id else model_id
        self._load_stage = stage
        self._load_short = short

        if stage == "start":
            self._load_start_ts  = time.monotonic()
            self._last_dl_pct    = -1
            self._load_hint_shown = False
            self._set_status(f"Loading {short}…", busy=True)
            self.append_info("Initialising model…")
        elif stage == "download_start":
            self._set_status(f"Downloading {short}…", busy=True)
            self.append_info("Downloading model files…")
        elif stage == "download":
            pct  = int(payload.get("progress_pct", 0))
            fname = payload.get("file", "")
            txt  = f"Downloading {short}: {pct}%"
            if fname:
                txt += f" ({fname})"
            self._set_status(txt, busy=True)
            if pct in (10, 25, 50, 75, 90, 100) and pct != self._last_dl_pct:
                self.append_info(f"Download: {pct}%")
                self._last_dl_pct = pct
        elif stage == "download_done":
            self._set_status(f"Download complete: {short}", busy=True)
        elif stage == "download_retry":
            attempt = int(payload.get("attempt", 1))
            ma = int(payload.get("max_attempts", 1))
            self._set_status(f"Retrying download ({attempt}/{ma})…", busy=True)
        elif stage == "tokenizer":
            self._set_status(f"Loading tokenizer: {short}…", busy=True)
        elif stage == "weights":
            self._set_status(f"Loading weights: {short}…", busy=True)
        elif stage == "device_selected":
            dev = payload.get("selected_device", "cpu")
            tv  = payload.get("torch_version", "")
            self.append_info(f"Device: {dev}  (torch {tv})")
        elif stage == "device_warning":
            self.append_info(str(payload.get("message", "Device fallback to CPU")))
        elif stage == "done":
            self._set_status("Model ready")
            self.append_info(f"✓ Model loaded: {model_id}")
        elif stage == "error":
            err = payload.get("error", "unknown error")
            self._set_status(f"Model load failed: {err[:60]}")
            self.append_info(f"✗ Model load failed: {err}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_page_loaded(self, ok: bool) -> None:
        self._page_ready = True
        # Install suggestion callback in JS so chip clicks reach Python
        self._web.page().runJavaScript(
            "window._suggestionCallback = function(t) { "
            "  window._agSuggestion = t; "
            "};"
        )
        # Replay any calls that were queued before load finished
        for js in self._pending_calls:
            self._web.page().runJavaScript(js)
        self._pending_calls.clear()

    def _js(self, script: str) -> None:
        """Run JS on the page, queuing it if the page isn't ready yet."""
        if self._page_ready:
            self._web.page().runJavaScript(script)
        else:
            self._pending_calls.append(script)

    def _set_status(self, text: str, busy: bool = False) -> None:
        if busy:
            self._status_lbl.setStyleSheet("color:#f59e0b; font-size:12px; background:transparent;")
        else:
            self._status_lbl.setStyleSheet("color:#475569; font-size:12px; background:transparent;")
        self._status_lbl.setText(text)
