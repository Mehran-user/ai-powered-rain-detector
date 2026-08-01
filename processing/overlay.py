import logging
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("rain_logger")

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
    "/usr/share/fonts/TTF/DejaVuSerif-Bold.ttf",
    "/Library/Fonts/Times New Roman Bold.ttf",
    "C:/Windows/Fonts/timesbd.ttf",
]

_font_cache = {}


def _find_font():
    for candidate in _FONT_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    return None


def annotate(image_bgr, lines, font_size_pt, dpi=96, margin=24,
             stroke_width=2, text_color=(255, 255, 255),
             stroke_color=(0, 0, 0)):
    font_size_px = int(round(font_size_pt * dpi / 72.0))
    font = _load_font(font_size_px)
    pil = Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    max_width = pil.width - 2 * margin
    y = margin
    for line in lines:
        if not line:
            continue
        for wrapped in _wrap(draw, font, line, max_width):
            draw.text(
                (margin, y),
                wrapped,
                font=font,
                fill=text_color,
                stroke_width=stroke_width,
                stroke_fill=stroke_color,
            )
            y += int(font_size_px * 1.3)
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def _load_font(font_size_px):
    if font_size_px in _font_cache:
        return _font_cache[font_size_px]
    font_path = _find_font()
    if font_path:
        font = ImageFont.truetype(font_path, font_size_px)
    else:
        logger.warning("No serif bold font found; using default font.")
        font = ImageFont.load_default()
    _font_cache[font_size_px] = font
    return font


def _wrap(draw, font, text, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines
