"""
Agentic - Reusable UI Components
==================================
Custom tkinter widgets that enforce the Agentic design system.
All widgets accept a Palette for consistent theming.
"""
from __future__ import annotations

import csv
import io
import re
import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import Any, Callable

from ui.theme import FONTS, M, Palette
from ui.icon_manager import get_default_icon_manager


ICON_GLYPH_FALLBACKS: dict[str, str] = {
    "attach": "📎",
    "voice": "🎙",
    "send": "➤",
    "copy": "⧉",
    "regenerate": "↻",
    "delete": "✕",
    "brainstorm": "✦",
    "write": "✎",
    "analyze": "▦",
    "learn": "⌁",
    "chat": "◉",
    "memory": "◌",
    "settings": "⚙",
    "new": "＋",
}


# ---------------------------------------------------------------------------
# Styled Button (Enhanced with Icon Support)
# ---------------------------------------------------------------------------

class AgButton(tk.Button):
    """Flat, accent-coloured button with hover effects and optional icons."""

    def __init__(
        self,
        master: Any,
        pal: Palette,
        text: str = "",
        command: Callable | None = None,
        kind: str = "primary",   # "primary" | "ghost" | "danger"
        icon: str | None = None,  # Icon name to load from icon library
        icon_size: int = 20,      # Icon size in pixels
        **kw: Any,
    ) -> None:
        self._pal = pal
        self._kind = kind
        self._icon = icon
        self._icon_size = icon_size
        self._photo = None  # Keep reference to prevent garbage collection

        bg, fg, active_bg = self._colours()
        font = kw.pop("font", (FONTS.family_ui, FONTS.size_sm, "normal"))
        padx = kw.pop("padx", M.padding_md)
        pady = kw.pop("pady", M.padding_sm)
        
        # Try to load icon if specified
        button_text = text
        button_image = None
        
        if icon:
            icon_mgr = get_default_icon_manager()
            button_image = icon_mgr.get_icon(icon, size=icon_size)
            if button_image:
                self._photo = button_image  # Keep reference
            else:
                # Icon not found, use glyph fallback so buttons still look iconized.
                glyph = ICON_GLYPH_FALLBACKS.get(icon, "◻")
                button_text = f"{glyph} {text}".strip()
        
        super().__init__(
            master,
            text=button_text,
            image=button_image,
            compound="left" if (button_image and text) else "none",
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=fg,
            relief="flat",
            cursor="hand2",
            font=font,
            padx=padx,
            pady=pady,
            borderwidth=0,
            highlightthickness=0,
            **kw,
        )
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _colours(self) -> tuple[str, str, str]:
        pal = self._pal
        if self._kind == "primary":
            return pal.accent, "#ffffff", pal.accent_hover
        if self._kind == "danger":
            return pal.danger, "#ffffff", "#dc2626"
        if self._kind == "secondary":
            return pal.border, pal.fg_primary, pal.bg_hover
        return pal.bg_base, pal.fg_muted, pal.bg_hover

    def _on_enter(self, _: Any) -> None:
        _, _, active_bg = self._colours()
        self.config(bg=active_bg)

    def _on_leave(self, _: Any) -> None:
        bg, _, _ = self._colours()
        self.config(bg=bg)


# ---------------------------------------------------------------------------
# Styled Entry
# ---------------------------------------------------------------------------

class AgEntry(tk.Entry):
    """Modern text input field with rounded appearance and proper focus states."""

    def __init__(self, master: Any, pal: Palette, **kw: Any) -> None:
        font = kw.pop("font", (FONTS.family_ui, FONTS.size_md))
        super().__init__(
            master,
            bg=pal.bg_input,
            fg=pal.fg_primary,
            insertbackground=pal.accent,
            selectbackground=pal.accent_dim,
            selectforeground=pal.fg_primary,
            relief="flat",
            highlightthickness=2,
            highlightcolor=pal.accent,
            highlightbackground=pal.border_dim,
            font=font,
            **kw,
        )


# ---------------------------------------------------------------------------
# Styled Label
# ---------------------------------------------------------------------------

class AgLabel(tk.Label):
    def __init__(
        self,
        master: Any,
        pal: Palette,
        text: str = "",
        size: int | None = None,
        bold: bool = False,
        muted: bool = False,
        **kw: Any,
    ) -> None:
        weight = "bold" if bold else "normal"
        fg = kw.pop("fg", pal.fg_muted if muted else pal.fg_primary)
        bg = kw.pop("bg", pal.bg_base)
        font = kw.pop("font", (FONTS.family_ui, size or FONTS.size_md, weight))
        super().__init__(
            master,
            text=text,
            bg=bg,
            fg=fg,
            font=font,
            **kw,
        )


# ---------------------------------------------------------------------------
# Styled Frame
# ---------------------------------------------------------------------------

class AgFrame(tk.Frame):
    def __init__(self, master: Any, pal: Palette, raised: bool = False, **kw: Any) -> None:
        bg = pal.bg_raised if raised else pal.bg_base
        super().__init__(master, bg=kw.pop("bg", bg), **kw)


# ---------------------------------------------------------------------------
# Scrollable Text Display (read-only)
# ---------------------------------------------------------------------------

class ScrolledText(tk.Frame):
    """Read-only scrollable text widget with syntax-aware colouring."""

    def __init__(self, master: Any, pal: Palette, **kw: Any) -> None:
        text_bg = kw.pop("bg", pal.bg_base)
        super().__init__(master, bg=text_bg)
        self._pal = pal
        self._link_tag_counter = 0

        self.text = tk.Text(
            self,
            bg=text_bg,
            fg=pal.fg_primary,
            insertbackground=pal.accent,
            selectbackground=pal.accent_dim,
            selectforeground=pal.fg_primary,
            relief="flat",
            wrap="word",
            cursor="arrow",
            state="disabled",
            font=(FONTS.family_ui, FONTS.size_md),
            padx=M.padding_lg,
            pady=M.padding_lg,
            spacing1=8,
            spacing2=4,
            spacing3=12,
            **kw,
        )
        sb = tk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.config(yscrollcommand=sb.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Chat tags tuned for clear user/assistant separation (Instagram-like)
        self.text.tag_config("user", foreground=pal.fg_primary, font=(FONTS.family_ui, FONTS.size_sm, "bold"))
        self.text.tag_config("assistant", foreground=pal.fg_primary, font=(FONTS.family_ui, FONTS.size_sm, "bold"))
        self.text.tag_config(
            "user_label",
            foreground=pal.fg_primary,
            font=(FONTS.family_ui, FONTS.size_sm, "bold"),
            lmargin1=300,
            lmargin2=300,
            rmargin=28,
            justify="right",
        )
        self.text.tag_config(
            "assistant_label",
            foreground=pal.fg_primary,
            font=(FONTS.family_ui, FONTS.size_sm, "bold"),
            lmargin1=28,
            lmargin2=28,
            rmargin=300,
        )
        self.text.tag_config(
            "timestamp_user",
            foreground=pal.fg_dim,
            font=(FONTS.family_ui, FONTS.size_xs),
            lmargin1=300,
            lmargin2=300,
            rmargin=28,
            justify="right",
        )
        self.text.tag_config(
            "timestamp",
            foreground=pal.fg_dim,
            font=(FONTS.family_ui, FONTS.size_xs),
            lmargin1=28,
            lmargin2=28,
            rmargin=300,
        )
        self.text.tag_config(
            "user_bubble",
            background="#0095f6",
            foreground="#ffffff",
            font=(FONTS.family_ui, FONTS.size_md),
            lmargin1=300,
            lmargin2=300,
            rmargin=28,
            justify="right",
            spacing1=4,
            spacing3=10,
        )
        self.text.tag_config(
            "assistant_bubble",
            background="#f3f4f6",
            foreground=pal.fg_primary,
            font=(FONTS.family_ui, FONTS.size_md),
            lmargin1=28,
            lmargin2=28,
            rmargin=300,
            spacing1=4,
            spacing3=10,
        )
        self.text.tag_config(
            "reasoning",
            foreground=pal.fg_muted,
            font=(FONTS.family_ui, FONTS.size_xs),
            lmargin1=28,
            lmargin2=28,
            rmargin=300,
            spacing3=6,
        )
        self.text.tag_config("system", foreground=pal.warn, font=(FONTS.family_ui, FONTS.size_sm, "bold"), background="#fffbeb")
        self.text.tag_config("skill", foreground=pal.info, font=(FONTS.family_code, FONTS.size_sm, "bold"), background="#eff6ff")
        self.text.tag_config("error", foreground=pal.danger, font=(FONTS.family_ui, FONTS.size_md, "bold"), background="#fef2f2")
        self.text.tag_config("info", foreground=pal.info, font=(FONTS.family_ui, FONTS.size_sm))
        self.text.tag_config("dim", foreground=pal.fg_dim, font=(FONTS.family_ui, FONTS.size_xs))

        # Rich content tags
        self.text.tag_config("md_bold", font=(FONTS.family_ui, FONTS.size_md, "bold"))
        self.text.tag_config("md_italic", font=(FONTS.family_ui, FONTS.size_md, "italic"))
        self.text.tag_config("md_inline_code", background=pal.bg_raised, foreground=pal.info, font=(FONTS.family_code, FONTS.size_sm))
        self.text.tag_config("md_codeblock", background=pal.bg_input, foreground=pal.fg_primary, font=(FONTS.family_code, FONTS.size_sm), lmargin1=20, lmargin2=20, rmargin=20)
        self.text.tag_config("md_math_inline", background=pal.bg_raised, foreground=pal.ok, font=(FONTS.family_code, FONTS.size_sm, "italic"))
        self.text.tag_config("md_math_block", background=pal.bg_input, foreground=pal.ok, font=(FONTS.family_code, FONTS.size_sm), lmargin1=20, lmargin2=20, rmargin=20)
        self.text.tag_config("md_table", background=pal.bg_input, foreground=pal.fg_primary, font=(FONTS.family_code, FONTS.size_sm), lmargin1=20, lmargin2=20, rmargin=20)
        self.text.tag_config("md_table_header", background=pal.bg_raised, foreground=pal.accent, font=(FONTS.family_code, FONTS.size_sm, "bold"), lmargin1=20, lmargin2=20, rmargin=20)
        self.text.tag_config("md_heading_h1", foreground=pal.fg_primary, font=(FONTS.family_ui, FONTS.size_h2, "bold"), spacing1=10, spacing3=6)
        self.text.tag_config("md_heading_h2", foreground=pal.fg_primary, font=(FONTS.family_ui, FONTS.size_lg, "bold"), spacing1=8, spacing3=4)
        self.text.tag_config("md_heading_h3", foreground=pal.fg_primary, font=(FONTS.family_ui, FONTS.size_md, "bold"), spacing1=6, spacing3=2)
        self.text.tag_config("md_quote", foreground=pal.fg_muted, background=pal.bg_raised, font=(FONTS.family_ui, FONTS.size_sm, "italic"), lmargin1=20, lmargin2=24, rmargin=20)
        self.text.tag_config("md_bullet", foreground=pal.fg_primary, font=(FONTS.family_ui, FONTS.size_md), lmargin1=18, lmargin2=28)
        self.text.tag_config("md_hr", foreground=pal.border, font=(FONTS.family_code, FONTS.size_sm))
        self.text.tag_config("md_link", foreground=pal.info, underline=True)
        self.text.tag_config("md_code_lang", foreground=pal.fg_muted, font=(FONTS.family_code, FONTS.size_xs, "italic"), lmargin1=20, lmargin2=20, rmargin=20)

    def append(self, text: str, tag: str = "assistant") -> None:
        self.text.config(state="normal")
        self.text.insert("end", text, tag)
        self.text.see("end")
        self.text.config(state="disabled")

    def get_end_index(self) -> str:
        """Return current end index (excluding trailing newline sentinel)."""
        return self.text.index("end-1c")

    def append_markdown(self, text: str, base_tag: str = "assistant") -> None:
        """Append markdown-like rich content to the end of the text widget."""
        self.text.config(state="normal")
        self._insert_markdown(text, base_tag=base_tag, at_index="end")
        self.text.see("end")
        self.text.config(state="disabled")

    def replace_range_with_markdown(self, start_index: str, end_index: str, text: str, base_tag: str = "assistant") -> None:
        """Replace an existing range with parsed markdown content."""
        self.text.config(state="normal")
        self.text.delete(start_index, end_index)
        self._insert_markdown(text, base_tag=base_tag, at_index=start_index)
        self.text.see("end")
        self.text.config(state="disabled")

    def _insert_markdown(self, text: str, base_tag: str, at_index: str = "end") -> None:
        lines = text.splitlines(keepends=True)
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                self.text.insert(at_index, line, (base_tag,))
                i += 1
                continue

            # Headings
            if stripped.startswith("### "):
                self.text.insert(at_index, stripped[4:] + "\n", (base_tag, "md_heading_h3"))
                i += 1
                continue
            if stripped.startswith("## "):
                self.text.insert(at_index, stripped[3:] + "\n", (base_tag, "md_heading_h2"))
                i += 1
                continue
            if stripped.startswith("# "):
                self.text.insert(at_index, stripped[2:] + "\n", (base_tag, "md_heading_h1"))
                i += 1
                continue

            # Horizontal rule
            if stripped in ("---", "***", "___"):
                self.text.insert(at_index, "-" * 52 + "\n", (base_tag, "md_hr"))
                i += 1
                continue

            # Block quote
            if stripped.startswith(">"):
                quote_text = stripped[1:].lstrip()
                self.text.insert(at_index, quote_text + "\n", (base_tag, "md_quote"))
                i += 1
                continue

            # Bullet or numbered list item
            bullet_match = re.match(r"^\s*([-*])\s+(.*)$", line)
            num_match = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
            if bullet_match:
                self.text.insert(at_index, "- " + bullet_match.group(2).rstrip("\n") + "\n", (base_tag, "md_bullet"))
                i += 1
                continue
            if num_match:
                numbered_text = num_match.group(2).rstrip("\n")
                self.text.insert(at_index, f"{num_match.group(1)}. {numbered_text}\n", (base_tag, "md_bullet"))
                i += 1
                continue

            # Fenced code block ```lang ... ```
            if stripped.startswith("```"):
                lang = stripped[3:].strip()
                i += 1
                code_lines: list[str] = []
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                if i < len(lines) and lines[i].strip().startswith("```"):
                    i += 1
                if lang:
                    self.text.insert(at_index, f"{lang}\n", (base_tag, "md_code_lang"))
                code_text = "".join(code_lines)
                if not code_text.endswith("\n"):
                    code_text += "\n"
                self.text.insert(at_index, code_text, (base_tag, "md_codeblock"))
                continue

            # Block math $$ ... $$
            if stripped == "$$":
                i += 1
                math_lines: list[str] = []
                while i < len(lines) and lines[i].strip() != "$$":
                    math_lines.append(lines[i])
                    i += 1
                if i < len(lines) and lines[i].strip() == "$$":
                    i += 1
                math_text = "".join(math_lines)
                if not math_text.endswith("\n"):
                    math_text += "\n"
                self.text.insert(at_index, math_text, (base_tag, "md_math_block"))
                continue

            # Markdown table
            if self._looks_like_markdown_table_header(lines, i):
                table_rows: list[list[str]] = []
                header = self._split_md_table_row(lines[i])
                table_rows.append(header)
                i += 2  # skip header + separator
                while i < len(lines) and "|" in lines[i]:
                    row = self._split_md_table_row(lines[i])
                    if not row:
                        break
                    table_rows.append(row)
                    i += 1
                self._insert_text_table(table_rows, base_tag)
                continue

            # CSV-like table block
            if self._looks_like_csv_line(line):
                csv_lines = [line]
                i += 1
                while i < len(lines) and self._looks_like_csv_line(lines[i]):
                    csv_lines.append(lines[i])
                    i += 1
                rows = self._parse_csv_lines(csv_lines)
                if len(rows) >= 2 and all(len(r) == len(rows[0]) for r in rows if r):
                    self._insert_text_table(rows, base_tag)
                else:
                    for raw in csv_lines:
                        self._insert_inline_styles(raw, base_tag, at_index)
                continue

            self._insert_inline_styles(line, base_tag, at_index)
            i += 1

    def _insert_inline_styles(self, text: str, base_tag: str, at_index: str = "end") -> None:
        i = 0
        while i < len(text):
            # Markdown link [label](url)
            if text[i] == "[":
                m = re.match(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", text[i:])
                if m:
                    label, url = m.group(1), m.group(2)
                    self._insert_clickable_link(label, url, base_tag, at_index)
                    i += len(m.group(0))
                    continue

            # Raw URL
            url_match = re.match(r"https?://[^\s)]+", text[i:])
            if url_match:
                url = url_match.group(0)
                self._insert_clickable_link(url, url, base_tag, at_index)
                i += len(url)
                continue

            # Inline code
            if text[i] == "`":
                j = text.find("`", i + 1)
                if j != -1:
                    self.text.insert(at_index, text[i + 1:j], (base_tag, "md_inline_code"))
                    i = j + 1
                    continue

            # Bold **...** or __...__
            if text.startswith("**", i) or text.startswith("__", i):
                marker = text[i:i + 2]
                j = text.find(marker, i + 2)
                if j != -1:
                    self.text.insert(at_index, text[i + 2:j], (base_tag, "md_bold"))
                    i = j + 2
                    continue

            # Inline math $...$
            if text[i] == "$":
                j = text.find("$", i + 1)
                if j != -1:
                    self.text.insert(at_index, text[i + 1:j], (base_tag, "md_math_inline"))
                    i = j + 1
                    continue

            # Italic *...* or _..._
            if text[i] in "*_":
                marker = text[i]
                j = text.find(marker, i + 1)
                if j != -1:
                    self.text.insert(at_index, text[i + 1:j], (base_tag, "md_italic"))
                    i = j + 1
                    continue

            next_special = self._find_next_special(text, i)
            chunk = text[i:next_special]
            self.text.insert(at_index, chunk, (base_tag,))
            i = next_special

    def _insert_clickable_link(self, label: str, url: str, base_tag: str, at_index: str = "end") -> None:
        self._link_tag_counter += 1
        link_tag = f"md_link_{self._link_tag_counter}"
        self.text.tag_config(link_tag, foreground=self._pal.info, underline=True)
        self.text.tag_bind(link_tag, "<Enter>", lambda _: self.text.config(cursor="hand2"))
        self.text.tag_bind(link_tag, "<Leave>", lambda _: self.text.config(cursor="arrow"))
        self.text.tag_bind(link_tag, "<Button-1>", lambda _, u=url: webbrowser.open_new_tab(u))
        self.text.insert(at_index, label, (base_tag, "md_link", link_tag))

    @staticmethod
    def _find_next_special(text: str, start: int) -> int:
        specials = [text.find(ch, start) for ch in ("`", "*", "_", "$")]
        hits = [p for p in specials if p != -1]
        return min(hits) if hits else len(text)

    @staticmethod
    def _looks_like_markdown_table_header(lines: list[str], index: int) -> bool:
        if index + 1 >= len(lines):
            return False
        header = lines[index]
        sep = lines[index + 1]
        if "|" not in header or "|" not in sep:
            return False
        return bool(re.match(r"^\s*\|?\s*[:\-]+\s*(\|\s*[:\-]+\s*)+\|?\s*$", sep.strip()))

    @staticmethod
    def _split_md_table_row(line: str) -> list[str]:
        raw = line.strip().strip("|")
        if not raw:
            return []
        return [c.strip() for c in raw.split("|")]

    @staticmethod
    def _looks_like_csv_line(line: str) -> bool:
        candidate = line.strip()
        return bool(candidate) and candidate.count(",") >= 1 and "|" not in candidate

    @staticmethod
    def _parse_csv_lines(lines: list[str]) -> list[list[str]]:
        data = "".join(lines)
        reader = csv.reader(io.StringIO(data))
        return [row for row in reader if row]

    def _insert_text_table(self, rows: list[list[str]], base_tag: str) -> None:
        if not rows:
            return
        col_count = max(len(r) for r in rows)
        normalized = [r + [""] * (col_count - len(r)) for r in rows]
        widths = [max(len(row[c]) for row in normalized) for c in range(col_count)]

        header = normalized[0]
        header_line = " | ".join(header[c].ljust(widths[c]) for c in range(col_count)) + "\n"
        sep_line = "-+-".join("-" * widths[c] for c in range(col_count)) + "\n"
        self.text.insert("end", header_line, (base_tag, "md_table_header"))
        self.text.insert("end", sep_line, (base_tag, "md_table"))

        for row in normalized[1:]:
            row_line = " | ".join(row[c].ljust(widths[c]) for c in range(col_count)) + "\n"
            self.text.insert("end", row_line, (base_tag, "md_table"))

    def clear(self) -> None:
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")


# ---------------------------------------------------------------------------
# Sidebar Navigation Item
# ---------------------------------------------------------------------------

class NavItem(tk.Frame):
    """Clickable navigation row for the sidebar."""

    def __init__(
        self,
        master: Any,
        pal: Palette,
        label: str,
        icon: str = "•",
        icon_name: str | None = None,
        on_click: Callable | None = None,
    ) -> None:
        super().__init__(master, bg=pal.bg_deep, cursor="hand2")
        self._pal = pal
        self._on_click = on_click
        self._active = False
        self._photo = None

        icon_image = None
        if icon_name:
            icon_image = get_default_icon_manager().get_icon(icon_name, size=18)
            if icon_image:
                self._photo = icon_image

        self._icon_lbl = tk.Label(
            self,
            text=("" if icon_image else icon),
            image=icon_image,
            compound="left",
            bg=pal.bg_deep,
            fg=pal.fg_muted,
            font=(FONTS.family_ui, FONTS.size_md),
            padx=M.padding_sm, pady=M.padding_sm,
        )
        self._text_lbl = tk.Label(
            self, text=label, bg=pal.bg_deep, fg=pal.fg_muted,
            font=(FONTS.family_ui, FONTS.size_sm),
            anchor="w",
        )
        self._icon_lbl.pack(side="left")
        self._text_lbl.pack(side="left", fill="x", expand=True)

        for w in (self, self._icon_lbl, self._text_lbl):
            w.bind("<Button-1>", self._click)
            w.bind("<Enter>",    self._enter)
            w.bind("<Leave>",    self._leave)

    def _click(self, _: Any) -> None:
        if self._on_click:
            self._on_click()

    def _enter(self, _: Any) -> None:
        if not self._active:
            for w in (self, self._icon_lbl, self._text_lbl):
                w.config(bg=self._pal.bg_hover)

    def _leave(self, _: Any) -> None:
        if not self._active:
            for w in (self, self._icon_lbl, self._text_lbl):
                w.config(bg=self._pal.bg_deep)

    def set_active(self, active: bool) -> None:
        self._active = active
        bg = self._pal.accent_dim if active else self._pal.bg_deep
        fg = self._pal.accent_hover if active else self._pal.fg_muted
        for w in (self, self._icon_lbl, self._text_lbl):
            w.config(bg=bg)
        self._icon_lbl.config(fg=fg)
        self._text_lbl.config(fg=fg)


# ---------------------------------------------------------------------------
# Progress bar (custom, no ttk)
# ---------------------------------------------------------------------------

class AgProgressBar(tk.Canvas):
    """Thin horizontal progress bar."""

    def __init__(self, master: Any, pal: Palette, height: int = 4, **kw: Any) -> None:
        super().__init__(
            master, height=height, bg=pal.bg_raised,
            highlightthickness=0, **kw
        )
        self._pal = pal
        self._value = 0.0
        self.bind("<Configure>", self._redraw)

    def set_value(self, v: float) -> None:
        self._value = max(0.0, min(1.0, v))
        self._redraw()

    def _redraw(self, _: Any = None) -> None:
        self.delete("bar")
        w = self.winfo_width()
        h = self.winfo_height()
        filled = int(w * self._value)
        if filled > 0:
            self.create_rectangle(
                0, 0, filled, h,
                fill=self._pal.accent, outline="",
                tags="bar",
            )


# ---------------------------------------------------------------------------
# Suggested Actions (Like Gemini's Quick Actions)
# ---------------------------------------------------------------------------

class SuggestedAction(tk.Frame):
    """Colorful suggested action card with visual distinction."""

    ACTIONS_WITH_COLORS = {
        "brainstorm": ("#6366f1", "#e0e7ff"),  # indigo
        "write": ("#8b5cf6", "#f3e8ff"),       # purple
        "analyze": ("#3b82f6", "#eff6ff"),     # blue
        "learn": ("#06b6d4", "#ecfdf5"),       # cyan
    }

    def __init__(
        self,
        master: Any,
        pal: Palette,
        icon: str,
        label: str,
        icon_name: str | None = None,
        on_click: Callable | None = None,
    ) -> None:
        super().__init__(master, bg=pal.bg_base, cursor="hand2")
        self._pal = pal
        self._on_click = on_click
        self._photo = None

        # Get color for this action type
        accent_color, bg_color = self.ACTIONS_WITH_COLORS.get(
            icon_name or icon, 
            (pal.accent, pal.accent_dim)
        )

        # Configure grid for this frame
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Container with colored background
        frame = tk.Frame(
            self,
            bg=bg_color,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=accent_color,
            padx=M.padding_md,
            pady=M.padding_md,
        )
        frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        # Configure grid for frame content
        frame.grid_rowconfigure(0, weight=0)
        frame.grid_rowconfigure(1, weight=0)
        frame.grid_columnconfigure(0, weight=1)

        # Icon - try to load or use glyph
        icon_image = None
        if icon_name:
            icon_image = get_default_icon_manager().get_icon(icon_name, size=32)
            if icon_image:
                self._photo = icon_image

        if icon_image:
            icon_lbl = tk.Label(image=icon_image, bg=bg_color)
            icon_lbl.image = icon_image
            icon_lbl.grid(row=0, column=0, sticky="n", pady=(0, M.padding_xs))
        else:
            tk.Label(
                frame, text=icon, bg=bg_color, fg=accent_color,
                font=(FONTS.family_ui, FONTS.size_xl, "bold"),
            ).grid(row=0, column=0, sticky="n", pady=(0, M.padding_xs))

        # Label
        tk.Label(
            frame, text=label, bg=bg_color, fg=pal.fg_primary,
            font=(FONTS.family_ui, FONTS.size_sm, "bold"),
            wraplength=80,
        ).grid(row=1, column=0, sticky="ew")

        for w in (self, frame):
            w.bind("<Button-1>", self._click)
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)
        
        self._card = frame
        self._accent_color = accent_color
        self._bg_color = bg_color

    def _click(self, _: Any) -> None:
        if self._on_click:
            self._on_click()

    def _enter(self, _: Any) -> None:
        self._card.config(highlightbackground=self._accent_color)

    def _leave(self, _: Any) -> None:
        self._card.config(highlightbackground=self._accent_color)


class SuggestedActionsGrid(tk.Frame):
    """Grid of suggested actions shown in empty state (like Gemini)."""

    ACTIONS = [
        ("Brain", "Brainstorm", "brainstorm", "Generate creative ideas"),
        ("Pen", "Write", "write", "Draft content & essays"),
        ("Chart", "Analyze", "analyze", "Analyze data & concepts"),
        ("Book", "Learn", "learn", "Explain & teach concepts"),
    ]

    def __init__(
        self,
        master: Any,
        pal: Palette,
        on_action: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(master, bg=pal.bg_base)
        self._pal = pal
        self._on_action = on_action

        # Configure grid layout
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        # Title
        tk.Label(
            self,
            text="Quick Start",
            bg=pal.bg_base,
            fg=pal.fg_muted,
            font=(FONTS.family_ui, FONTS.size_sm),
        ).grid(row=0, column=0, sticky="ew", pady=(0, M.padding_md))

        # Grid of actions
        grid_frame = tk.Frame(self, bg=pal.bg_base)
        grid_frame.grid(row=1, column=0, sticky="ew")

        # Configure action grid layout
        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_rowconfigure(1, weight=1)
        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)

        for i, (icon_text, label, icon_name, tooltip) in enumerate(self.ACTIONS):
            row = i // 2
            col = i % 2
            action = SuggestedAction(
                grid_frame,
                pal,
                icon_text,
                label,
                icon_name=icon_name,
                on_click=lambda t=tooltip: self._on_action and self._on_action(t),
            )
            action.grid(row=row, column=col, padx=M.padding_sm, pady=M.padding_sm)


# ---------------------------------------------------------------------------
# Typing Indicator (Animated)
# ---------------------------------------------------------------------------

class TypingIndicator(tk.Frame):
    """Animated typing indicator with dots."""

    def __init__(self, master: Any, pal: Palette) -> None:
        super().__init__(master, bg=pal.bg_base)
        self._pal = pal
        self._frame = 0
        self._dots = [".", "..", "...", "...."]
        self._animating = False

        self._label = tk.Label(
            self,
            text="Thinking",
            bg=pal.bg_base,
            fg=pal.accent,
            font=(FONTS.family_ui, FONTS.size_sm, "bold"),
        )
        self._label.pack()

    def start(self) -> None:
        if not self._animating:
            self._animating = True
            self._animate()

    def stop(self) -> None:
        self._animating = False
        self._label.config(text="Thinking")

    def _animate(self) -> None:
        if not self._animating:
            return
        self._label.config(text=f"Thinking {self._dots[self._frame % len(self._dots)]}")
        self._frame += 1
        self.after(400, self._animate)


# ---------------------------------------------------------------------------
# Message Action Button Bar
# ---------------------------------------------------------------------------

class MessageActionBar(tk.Frame):
    """Buttons appearing on hover over a message (copy, regenerate, delete)."""

    def __init__(
        self,
        master: Any,
        pal: Palette,
        on_copy: Callable | None = None,
        on_regenerate: Callable | None = None,
        on_delete: Callable | None = None,
    ) -> None:
        super().__init__(master, bg=pal.bg_raised)
        self._pal = pal

        if on_copy:
            AgButton(
                self, pal, text="Copy",
                command=on_copy, kind="ghost",
                icon="copy",
                icon_size=16,
                padx=M.padding_sm, pady=2,
            ).pack(side="left", padx=M.padding_xs)

        if on_regenerate:
            AgButton(
                self, pal, text="Regenerate",
                command=on_regenerate, kind="ghost",
                icon="regenerate",
                icon_size=16,
                padx=M.padding_sm, pady=2,
            ).pack(side="left", padx=M.padding_xs)

        if on_delete:
            AgButton(
                self, pal, text="Remove",
                command=on_delete, kind="danger",
                icon="delete",
                icon_size=16,
                padx=M.padding_sm, pady=2,
            ).pack(side="left", padx=M.padding_xs)
