"""
Agentic - Icon Manager
======================
Manages loading and caching of icon images from files.
Supports PNG, GIF, and other Pillow-supported formats.

Usage:
    icon_mgr = IconManager("assets/icons")
    photo = icon_mgr.get_icon("attach", size=24)
    button = tk.Button(master, image=photo, ...)
    button.image = photo  # Keep reference!
"""
from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from typing import Optional

try:
    from PIL import Image, ImageTk
    from PIL import ImageDraw
except ImportError:  # Pillow is optional; the UI will fall back to text.
    Image = None  # type: ignore[assignment]
    ImageTk = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]


class IconManager:
    """Loads and caches icon images from a directory."""

    def __init__(self, icon_dir: str | Path = "assets/icons") -> None:
        """
        Initialize icon manager.
        
        Args:
            icon_dir: Directory containing icon files (PNG, GIF, etc)
        """
        self.icon_dir = Path(icon_dir)
        self._cache: dict[tuple[str, int], object] = {}
        
        if not self.icon_dir.exists():
            print(f"⚠️  Icon directory not found: {self.icon_dir}")
            print(f"Create it and add icon files: {self.icon_dir}/attach.png, voice.png, etc")

    def get_icon(
        self,
        name: str,
        size: int = 24,
        fallback_text: str = "⬚",
    ) -> object | None:
        """
        Load an icon by name at specified size.
        
        Args:
            name: Icon filename without extension (e.g., "attach", "voice")
            size: Icon size in pixels (height=size, width=size)
            fallback_text: Fallback if icon not found
            
        Returns:
            PhotoImage object or None if icon not found
        """
        # Check cache first
        cache_key = (name, size)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try to load icon file
        icon_path = self._try_icon_path(name)
        
        if not icon_path or not icon_path.exists():
            return self._generate_fallback_icon(name, size)

        if Image is None or ImageTk is None:
            print("⚠️  Pillow is not installed; icon images are disabled")
            return None

        try:
            # Load and resize image
            img = Image.open(icon_path)
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            
            # Create PhotoImage
            photo = ImageTk.PhotoImage(img)
            self._cache[cache_key] = photo
            return photo
            
        except Exception as e:
            print(f"❌ Error loading icon {name}: {e}")
            return self._generate_fallback_icon(name, size)

    def _generate_fallback_icon(self, name: str, size: int) -> object | None:
        """Generate a simple monochrome icon so UI never degrades to plain text buttons."""
        if Image is None or ImageTk is None or ImageDraw is None:
            return None

        cache_key = (f"fallback:{name}", size)
        if cache_key in self._cache:
            return self._cache[cache_key]

        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        stroke = max(2, size // 10)
        pad = max(2, size // 7)
        color = (126, 215, 255, 255)

        try:
            if name == "send":
                draw.polygon([(pad, size // 2), (size - pad, pad), (size - pad, size - pad)], outline=color, fill=None, width=stroke)
            elif name == "attach":
                draw.arc([pad, pad, size - pad, size - pad], start=30, end=320, fill=color, width=stroke)
                draw.arc([pad + stroke * 2, pad + stroke * 2, size - pad - stroke, size - pad - stroke], start=40, end=310, fill=color, width=stroke)
            elif name == "voice":
                draw.rounded_rectangle([size // 3, pad, size - size // 3, size - pad * 2], radius=stroke * 2, outline=color, width=stroke)
                draw.line([(size // 2, size - pad * 2), (size // 2, size - pad)], fill=color, width=stroke)
                draw.arc([size // 3 - stroke, size - pad * 2, size - size // 3 + stroke, size - pad // 2], start=0, end=180, fill=color, width=stroke)
            elif name == "copy":
                draw.rectangle([pad + stroke, pad, size - pad, size - pad - stroke], outline=color, width=stroke)
                draw.rectangle([pad, pad + stroke, size - pad - stroke, size - pad], outline=color, width=stroke)
            elif name == "delete":
                draw.rectangle([pad + stroke, size // 3, size - pad - stroke, size - pad], outline=color, width=stroke)
                draw.line([(pad + stroke, size // 3), (size - pad - stroke, size // 3)], fill=color, width=stroke)
                draw.line([(size // 3, pad + stroke), (size // 3, size // 3)], fill=color, width=stroke)
                draw.line([(size - size // 3, pad + stroke), (size - size // 3, size // 3)], fill=color, width=stroke)
            elif name == "regenerate":
                draw.arc([pad, pad, size - pad, size - pad], start=35, end=315, fill=color, width=stroke)
                draw.polygon([(size - pad, size // 3), (size - pad, pad), (size - size // 3, pad + stroke)], fill=color)
            elif name == "settings":
                draw.ellipse([pad + stroke, pad + stroke, size - pad - stroke, size - pad - stroke], outline=color, width=stroke)
                draw.ellipse([size // 2 - stroke, size // 2 - stroke, size // 2 + stroke, size // 2 + stroke], fill=color)
            elif name == "memory":
                draw.ellipse([pad, pad, size - pad, size - pad], outline=color, width=stroke)
                draw.arc([pad + stroke * 2, pad + stroke * 2, size - pad - stroke * 2, size - pad - stroke * 2], start=40, end=320, fill=color, width=stroke)
            elif name == "chat":
                draw.rounded_rectangle([pad, pad, size - pad, size - pad - stroke], radius=stroke * 2, outline=color, width=stroke)
                draw.polygon([(size // 3, size - pad - stroke), (size // 2, size - pad - stroke), (size // 3 + stroke, size - pad // 2)], outline=color, fill=None)
            else:
                draw.ellipse([pad, pad, size - pad, size - pad], outline=color, width=stroke)
        except Exception:
            return None

        photo = ImageTk.PhotoImage(canvas)
        self._cache[cache_key] = photo
        return photo

    def _try_icon_path(self, name: str) -> Optional[Path]:
        """Try to find icon file with various extensions."""
        for ext in [".png", ".gif", ".jpg", ".jpeg", ".ppm"]:
            path = self.icon_dir / f"{name}{ext}"
            if path.exists():
                return path
        return None

    def has_icon(self, name: str) -> bool:
        """Check if icon exists."""
        return self._try_icon_path(name) is not None

    def list_icons(self) -> list[str]:
        """List all available icons in the directory."""
        if not self.icon_dir.exists():
            return []
        
        icons = set()
        for file in self.icon_dir.iterdir():
            if file.suffix.lower() in [".png", ".gif", ".jpg", ".jpeg", ".ppm"]:
                icons.add(file.stem)
        return sorted(list(icons))

    def clear_cache(self) -> None:
        """Clear cached icons to free memory."""
        self._cache.clear()


# Global instance
_icon_manager: Optional[IconManager] = None


def init_icon_manager(icon_dir: str | Path = "assets/icons") -> IconManager:
    """Initialize global icon manager."""
    global _icon_manager
    _icon_manager = IconManager(icon_dir)
    return _icon_manager


def get_default_icon_manager() -> IconManager:
    """Get or create default icon manager."""
    global _icon_manager
    if _icon_manager is None:
        _icon_manager = IconManager()
    return _icon_manager
