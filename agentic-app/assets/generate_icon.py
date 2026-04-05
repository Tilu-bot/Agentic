"""
Agentic - Asset Generator
==========================
Generates a simple PNG icon for the application.
Run this once to create the icon files needed by PyInstaller.

Usage:
    python generate_icon.py
"""
import struct
import zlib

# Minimal 32x32 PNG with an "A" emblem – pure stdlib, no Pillow needed
_W, _H = 32, 32

def _u32be(n: int) -> bytes:
    return struct.pack(">I", n)

def _chunk(name: bytes, data: bytes) -> bytes:
    raw = name + data
    return _u32be(len(data)) + raw + _u32be(zlib.crc32(raw) & 0xFFFFFFFF)

def _make_icon_png(filename: str) -> None:
    # Draw a simple 32x32 icon: dark bg + accent hex shape
    rows = []
    for y in range(_H):
        row_pixels = b""
        for x in range(_W):
            # Rounded dark background
            cx, cy = x - 16, y - 16
            if cx * cx + cy * cy < 200:          # circle mask
                # accent color pixel
                r, g, b = 0x6c, 0x8e, 0xf5
            else:
                r, g, b = 0x0d, 0x0f, 0x14
            row_pixels += bytes([r, g, b])
        rows.append(b"\x00" + row_pixels)         # filter byte

    raw = zlib.compress(b"".join(rows))
    ihdr_data = _u32be(_W) + _u32be(_H) + bytes([8, 2, 0, 0, 0])  # 8-bit RGB
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr_data)
        + _chunk(b"IDAT", raw)
        + _chunk(b"IEND", b"")
    )
    with open(filename, "wb") as f:
        f.write(png)
    print(f"Created: {filename}")

if __name__ == "__main__":
    import os
    assets_dir = os.path.dirname(__file__)
    _make_icon_png(os.path.join(assets_dir, "icon.png"))
    print("Icon generated. For Windows/macOS packaging, convert to .ico/.icns manually.")
