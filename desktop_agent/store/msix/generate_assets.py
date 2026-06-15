# -*- coding: utf-8 -*-
"""Vygeneruje PNG ikony pro MSIX balíček (Assets/). Spuštění: python store/msix/generate_assets.py"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, "Assets")

# Barvy z web_app/static/logo/dokucheck-icon.svg
BG = (30, 41, 59)       # #1E293B
DOC = (51, 65, 85)       # #334155
CHECK = (22, 163, 74)    # #16A34A


def _draw_icon(size):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise SystemExit(
            "Pro generování ikon nainstalujte Pillow: pip install pillow"
        )
    img = Image.new("RGBA", (size, size), BG + (255,))
    draw = ImageDraw.Draw(img)
    pad = size * 0.12
    doc_w = size * 0.45
    doc_h = size * 0.5
    x0, y0 = pad, pad
    x1, y1 = x0 + doc_w, y0 + doc_h
    draw.rectangle([x0, y0, x1, y1], fill=DOC + (255,))
    fold = size * 0.12
    draw.polygon([(x1 - fold, y0), (x1, y0 + fold), (x1 - fold, y0 + fold)], fill=BG + (255,))
    sw = max(2, int(size * 0.1))
    cx, cy = size * 0.5, size * 0.58
    draw.line([(size * 0.32, cy), (size * 0.46, cy + size * 0.14)], fill=CHECK + (255,), width=sw)
    draw.line([(size * 0.46, cy + size * 0.14), (size * 0.78, size * 0.32)], fill=CHECK + (255,), width=sw)
    return img


def _save_scaled(name, size):
    os.makedirs(ASSETS_DIR, exist_ok=True)
    img = _draw_icon(size)
    path = os.path.join(ASSETS_DIR, name)
    img.save(path, "PNG")
    print("OK:", path)


def main():
    _save_scaled("Square44x44Logo.png", 44)
    _save_scaled("Square150x150Logo.png", 150)
    _save_scaled("StoreLogo.png", 50)
    wide = _draw_icon(150)
    try:
        from PIL import Image
        canvas = Image.new("RGBA", (310, 150), BG + (255,))
        canvas.paste(wide, ((310 - 150) // 2, 0))
        path = os.path.join(ASSETS_DIR, "Wide310x150Logo.png")
        canvas.save(path, "PNG")
        print("OK:", path)
    except ImportError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
