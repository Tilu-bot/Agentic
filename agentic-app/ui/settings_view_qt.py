"""
Agentic - Settings View (PyQt6)
=================================
Configuration panel: model selection, device, HF token, memory limits,
parallel task cap, and appearance.  All changes are saved to the Config
singleton on "Save Settings".
"""
from __future__ import annotations

import threading
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from model.gemma_nexus import KNOWN_MODELS, MODEL_FAMILIES
from utils.config import cfg

_DEVICES = ["auto", "cpu", "cuda", "mps"]


class SettingsViewQt(QWidget):
    """Settings panel."""

    def __init__(
        self,
        parent: QWidget | None = None,
        on_theme_change: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_theme_change = on_theme_change
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Top bar ──────────────────────────────────────────────────
        top_bar = QWidget(self)
        top_bar.setStyleSheet("background:#1a1d27; border-bottom:1px solid #252840;")
        top_bar.setFixedHeight(64)
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(24, 0, 24, 0)

        title_wrap = QWidget(top_bar)
        title_wrap.setStyleSheet("background:transparent;")
        tw_l = QVBoxLayout(title_wrap)
        tw_l.setContentsMargins(0, 0, 0, 0)
        tw_l.setSpacing(1)
        lbl = QLabel("Settings", title_wrap)
        lbl.setObjectName("SectionTitle")
        lbl.setStyleSheet("font-size:18px; font-weight:700; color:#e2e8f0; background:transparent;")
        sub = QLabel("Configure model, memory, and appearance.", title_wrap)
        sub.setObjectName("SectionSubtitle")
        tw_l.addWidget(lbl)
        tw_l.addWidget(sub)
        tb_layout.addWidget(title_wrap)
        outer.addWidget(top_bar)

        # ── Scrollable form area ──────────────────────────────────────
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background:#0f1117;")

        form_container = QWidget()
        form_container.setStyleSheet("background:#0f1117;")
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(32, 24, 32, 32)
        form_layout.setSpacing(0)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ── Model section ─────────────────────────────────────────────
        self._add_section_header(form_layout, "Model")
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setContentsMargins(0, 0, 0, 20)

        # Model ID + quick-pick
        model_row = QWidget()
        model_row.setStyleSheet("background:transparent;")
        mr_layout = QHBoxLayout(model_row)
        mr_layout.setContentsMargins(0, 0, 0, 0)
        mr_layout.setSpacing(8)

        self._model_edit = QLineEdit(model_row)
        self._model_edit.setText(cfg.get("model_id", KNOWN_MODELS[0]))
        self._model_edit.setPlaceholderText("e.g. google/gemma-3-1b-it")

        self._model_combo = QComboBox(model_row)
        self._model_combo.setFixedWidth(230)
        self._model_combo.addItem("Quick pick…")
        for family, models in MODEL_FAMILIES.items():
            self._model_combo.addItem(f"── {family} ──")
            idx = self._model_combo.count() - 1
            self._model_combo.model().item(idx).setEnabled(False)
            for mid in models:
                self._model_combo.addItem(mid)
        self._model_combo.currentTextChanged.connect(self._on_quick_pick)

        mr_layout.addWidget(self._model_edit, stretch=1)
        mr_layout.addWidget(self._model_combo)
        form.addRow(self._lbl("HuggingFace Model ID"), model_row)

        # HF token
        self._token_edit = QLineEdit()
        self._token_edit.setText(cfg.get("hf_token", ""))
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_edit.setPlaceholderText("hf_…  (leave blank for public models)")
        form.addRow(self._lbl("HuggingFace Token (optional)"), self._token_edit)

        # Device radio buttons
        device_row = QWidget()
        device_row.setStyleSheet("background:transparent;")
        dr_layout = QHBoxLayout(device_row)
        dr_layout.setContentsMargins(0, 0, 0, 0)
        dr_layout.setSpacing(16)
        self._device_radios: dict[str, QRadioButton] = {}
        current_device = cfg.get("device", "auto")
        for dev in _DEVICES:
            rb = QRadioButton(dev, device_row)
            rb.setChecked(dev == current_device)
            self._device_radios[dev] = rb
            dr_layout.addWidget(rb)
        dr_layout.addStretch()
        form.addRow(self._lbl("Device"), device_row)

        # 4-bit quantization
        self._q4_check = QCheckBox("4-bit quantization  (requires bitsandbytes + GPU)")
        self._q4_check.setChecked(cfg.get("quantize_4bit", False))
        form.addRow(self._lbl(""), self._q4_check)

        # Check availability button + status
        self._check_btn = QPushButton("Check model availability")
        self._check_btn.setObjectName("GhostButton")
        self._check_btn.setFixedWidth(220)
        self._check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_btn.clicked.connect(self._check_model)
        self._model_status_lbl = QLabel("")
        self._model_status_lbl.setObjectName("FormLabel")
        self._model_status_lbl.setWordWrap(True)

        check_row = QWidget()
        check_row.setStyleSheet("background:transparent;")
        chk_l = QVBoxLayout(check_row)
        chk_l.setContentsMargins(0, 0, 0, 0)
        chk_l.setSpacing(6)
        chk_l.addWidget(self._check_btn)
        chk_l.addWidget(self._model_status_lbl)
        form.addRow(self._lbl(""), check_row)

        form_layout.addLayout(form)

        # ── Memory section ────────────────────────────────────────────
        self._add_section_header(form_layout, "Memory")
        form2 = QFormLayout()
        form2.setSpacing(12)
        form2.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form2.setContentsMargins(0, 0, 0, 20)

        wm_row = QWidget()
        wm_row.setStyleSheet("background:transparent;")
        wm_l = QHBoxLayout(wm_row)
        wm_l.setContentsMargins(0, 0, 0, 0)
        wm_l.setSpacing(12)
        self._wm_slider = QSlider(Qt.Orientation.Horizontal, wm_row)
        self._wm_slider.setRange(5, 100)
        self._wm_slider.setValue(cfg.get("working_memory_limit", 20))
        self._wm_val_lbl = QLabel(str(self._wm_slider.value()), wm_row)
        self._wm_val_lbl.setObjectName("FormLabel")
        self._wm_val_lbl.setFixedWidth(36)
        self._wm_slider.valueChanged.connect(
            lambda v: self._wm_val_lbl.setText(str(v))
        )
        wm_l.addWidget(self._wm_slider, stretch=1)
        wm_l.addWidget(self._wm_val_lbl)
        form2.addRow(self._lbl("Working memory limit (turns)"), wm_row)

        # Context limit tokens
        self._ctx_spin = QSpinBox()
        self._ctx_spin.setRange(512, 131072)
        self._ctx_spin.setSingleStep(512)
        self._ctx_spin.setValue(cfg.get("context_limit_tokens", 4096))
        self._ctx_spin.setFixedWidth(120)
        form2.addRow(self._lbl("Context limit (tokens)"), self._ctx_spin)

        form_layout.addLayout(form2)

        # ── Execution section ─────────────────────────────────────────
        self._add_section_header(form_layout, "Execution")
        form3 = QFormLayout()
        form3.setSpacing(12)
        form3.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form3.setContentsMargins(0, 0, 0, 20)

        pt_row = QWidget()
        pt_row.setStyleSheet("background:transparent;")
        pt_l = QHBoxLayout(pt_row)
        pt_l.setContentsMargins(0, 0, 0, 0)
        pt_l.setSpacing(12)
        self._pt_slider = QSlider(Qt.Orientation.Horizontal, pt_row)
        self._pt_slider.setRange(1, 12)
        self._pt_slider.setValue(cfg.get("max_parallel_tasks", 4))
        self._pt_val_lbl = QLabel(str(self._pt_slider.value()), pt_row)
        self._pt_val_lbl.setObjectName("FormLabel")
        self._pt_val_lbl.setFixedWidth(36)
        self._pt_slider.valueChanged.connect(
            lambda v: self._pt_val_lbl.setText(str(v))
        )
        pt_l.addWidget(self._pt_slider, stretch=1)
        pt_l.addWidget(self._pt_val_lbl)
        form3.addRow(self._lbl("Max parallel tasks"), pt_row)

        self._react_spin = QSpinBox()
        self._react_spin.setRange(1, 20)
        self._react_spin.setValue(cfg.get("react_max_iterations", 6))
        self._react_spin.setFixedWidth(120)
        form3.addRow(self._lbl("ReAct max iterations"), self._react_spin)

        form_layout.addLayout(form3)

        # ── Appearance section ────────────────────────────────────────
        self._add_section_header(form_layout, "Appearance")
        form4 = QFormLayout()
        form4.setSpacing(12)
        form4.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form4.setContentsMargins(0, 0, 0, 24)

        theme_row = QWidget()
        theme_row.setStyleSheet("background:transparent;")
        tr_l = QHBoxLayout(theme_row)
        tr_l.setContentsMargins(0, 0, 0, 0)
        tr_l.setSpacing(16)
        self._theme_dark  = QRadioButton("Dark",  theme_row)
        self._theme_light = QRadioButton("Light", theme_row)
        theme_val = cfg.get("theme", "dark")
        self._theme_dark.setChecked(theme_val == "dark")
        self._theme_light.setChecked(theme_val == "light")
        self._theme_dark.toggled.connect(self._apply_theme)
        tr_l.addWidget(self._theme_dark)
        tr_l.addWidget(self._theme_light)
        tr_l.addStretch()
        form4.addRow(self._lbl("Theme"), theme_row)

        form_layout.addLayout(form4)

        # ── Save button ───────────────────────────────────────────────
        save_row = QWidget()
        save_row.setStyleSheet("background:transparent;")
        sr_l = QHBoxLayout(save_row)
        sr_l.setContentsMargins(0, 0, 0, 0)
        sr_l.setSpacing(12)

        self._save_btn = QPushButton("Save Settings")
        self._save_btn.setFixedWidth(160)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._save)

        self._save_status_lbl = QLabel("")
        self._save_status_lbl.setObjectName("FormLabel")

        sr_l.addWidget(self._save_btn)
        sr_l.addWidget(self._save_status_lbl)
        sr_l.addStretch()
        form_layout.addWidget(save_row)

        scroll.setWidget(form_container)
        outer.addWidget(scroll, stretch=1)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setObjectName("FormLabel")
        l.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        return l

    def _add_section_header(self, layout: QVBoxLayout, text: str) -> None:
        lbl = QLabel(text)
        lbl.setObjectName("SectionHeader")
        lbl.setStyleSheet(
            "font-size:15px; font-weight:700; color:#e2e8f0; "
            "background:transparent; padding-top:16px; padding-bottom:8px;"
        )
        layout.addWidget(lbl)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background:#252840; max-height:1px; border:none;")
        divider.setFixedHeight(1)
        layout.addWidget(divider)
        # Spacer after divider
        spacer = QLabel("")
        spacer.setFixedHeight(8)
        spacer.setStyleSheet("background:transparent; border:none;")
        layout.addWidget(spacer)

    def _on_quick_pick(self, text: str) -> None:
        if text and text != "Quick pick…" and not text.startswith("──"):
            self._model_edit.setText(text)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _save(self) -> None:
        device = "auto"
        for dev, rb in self._device_radios.items():
            if rb.isChecked():
                device = dev
                break
        theme = "dark" if self._theme_dark.isChecked() else "light"
        cfg.update({
            "model_id":             self._model_edit.text().strip(),
            "hf_token":             self._token_edit.text().strip(),
            "device":               device,
            "quantize_4bit":        self._q4_check.isChecked(),
            "working_memory_limit": self._wm_slider.value(),
            "context_limit_tokens": self._ctx_spin.value(),
            "max_parallel_tasks":   self._pt_slider.value(),
            "react_max_iterations": self._react_spin.value(),
            "theme":                theme,
        })
        self._save_status_lbl.setStyleSheet("color:#10b981; font-size:13px;")
        self._save_status_lbl.setText("✓ Settings saved.")
        QTimer_once(2000, lambda: self._save_status_lbl.setText(""), self)

    def _apply_theme(self) -> None:
        theme = "dark" if self._theme_dark.isChecked() else "light"
        if self._on_theme_change:
            self._on_theme_change(theme)

    def _check_model(self) -> None:
        self._model_status_lbl.setStyleSheet("color:#f59e0b; font-size:12px;")
        self._model_status_lbl.setText("Checking…")
        model_id = self._model_edit.text().strip()

        def _check() -> None:
            try:
                from huggingface_hub import try_to_load_from_cache
                result = try_to_load_from_cache(model_id, "config.json")
                if result is not None:
                    msg    = f"✓ '{model_id}' found in local cache."
                    colour = "color:#10b981;"
                else:
                    msg    = f"'{model_id}' not cached — will be downloaded on first use."
                    colour = "color:#f59e0b;"
            except Exception as exc:
                msg    = f"✗ {exc}"
                colour = "color:#ef4444;"

            # Schedule UI update on main thread via a zero-delay timer trick
            self._model_status_lbl.setProperty("_pending_text",  msg)
            self._model_status_lbl.setProperty("_pending_style", colour)
            QTimer_once(0, self._apply_check_result, self)

        threading.Thread(target=_check, daemon=True).start()

    def _apply_check_result(self) -> None:
        txt   = self._model_status_lbl.property("_pending_text")  or ""
        style = self._model_status_lbl.property("_pending_style") or ""
        self._model_status_lbl.setStyleSheet(f"{style} font-size:12px;")
        self._model_status_lbl.setText(txt)


# ---------------------------------------------------------------------------
# Tiny helper: one-shot QTimer callback
# ---------------------------------------------------------------------------

def QTimer_once(ms: int, fn: Callable, parent: QWidget | None = None) -> None:
    from PyQt6.QtCore import QTimer
    t = QTimer(parent)
    t.setSingleShot(True)
    t.timeout.connect(fn)
    t.start(ms)


