"""
Agentic - ICO Icon Generator
==============================
Converts assets/icon.png → assets/icon.ico (multi-size ICO required by
PyInstaller on Windows and by the Inno Setup installer script).

Sizes included: 16, 32, 48, 64, 128, 256 px (standard Windows ICO sizes).

Run once before building the installer:
    python assets/generate_icon_ico.py

Requirements:
    pip install Pillow
"""

import struct
import sys
import zlib
from pathlib import Path

ASSETS = Path(__file__).parent
SRC_PNG = ASSETS / "icon.png"
OUT_ICO = ASSETS / "icon.ico"

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def _rgba_pixels(src: Path, size: int) -> bytes:
    """Return raw RGBA bytes for the icon at the given square size."""
    try:
        from PIL import Image  # type: ignore
        img = Image.open(src).convert("RGBA").resize((size, size), Image.LANCZOS)
        return img.tobytes()
    except ImportError:
        # Fallback: generate a simple solid-colour square (no Pillow)
        return _simple_rgba(size)


def _simple_rgba(size: int) -> bytes:
    """Minimal RGBA square: dark bg with accent circle."""
    rows = bytearray()
    cx, cy = size // 2, size // 2
    r2 = (size * size) // 4
    for y in range(size):
        for x in range(size):
            dx, dy = x - cx, y - cy
            if dx * dx + dy * dy < r2 * 0.6:
                rows += bytes([0x6C, 0x8E, 0xF5, 0xFF])
            else:
                rows += bytes([0x0D, 0x0F, 0x14, 0xFF])
    return bytes(rows)


def _png_bytes_from_rgba(rgba: bytes, size: int) -> bytes:
    """Encode raw RGBA bytes as a minimal PNG blob."""

    def u32be(n: int) -> bytes:
        return struct.pack(">I", n)

    def chunk(name: bytes, data: bytes) -> bytes:
        raw = name + data
        return u32be(len(data)) + raw + u32be(zlib.crc32(raw) & 0xFFFFFFFF)

    rows = []
    stride = size * 4
    for y in range(size):
        rows.append(b"\x00" + rgba[y * stride : (y + 1) * stride])
    idat = zlib.compress(b"".join(rows))

    ihdr = u32be(size) + u32be(size) + bytes([8, 6, 0, 0, 0])  # 8-bit RGBA
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )


def build_ico(src: Path, dest: Path, sizes: list[int]) -> None:
    """Build a multi-size ICO file from a source PNG."""
    entries: list[bytes] = []
    images: list[bytes] = []

    for size in sizes:
        rgba = _rgba_pixels(src, size)
        png = _png_bytes_from_rgba(rgba, size)
        images.append(png)

    # ICO header: 6 bytes
    count = len(sizes)
    header = struct.pack("<HHH", 0, 1, count)  # reserved, type=1 (ICO), count

    # Directory entries: 16 bytes each
    offset = 6 + count * 16
    for i, size in enumerate(sizes):
        img = images[i]
        w = size if size < 256 else 0  # 256 is encoded as 0 in ICO
        h = size if size < 256 else 0
        entries.append(
            struct.pack(
                "<BBBBHHII",
                w,       # width
                h,       # height
                0,       # colour count (0 = >256 colours)
                0,       # reserved
                1,       # colour planes
                32,      # bits per pixel
                len(img),
                offset,
            )
        )
        offset += len(img)

    with open(dest, "wb") as f:
        f.write(header)
        for e in entries:
            f.write(e)
        for img in images:
            f.write(img)

    print(f"Created: {dest}  ({count} sizes: {sizes})")


if __name__ == "__main__":
    if not SRC_PNG.exists():
        print(f"Source PNG not found: {SRC_PNG}")
        print("Run  python assets/generate_icon.py  first to create icon.png")
        sys.exit(1)
    build_ico(SRC_PNG, OUT_ICO, ICO_SIZES)
