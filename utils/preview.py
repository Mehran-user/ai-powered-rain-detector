import cv2
from PIL import Image

_CHARS = " .:-=+*#%@"


def ascii_preview(image_bgr, width=64):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    pil = Image.fromarray(gray)
    height = max(1, int(width * (pil.height / pil.width) * 0.5))
    pil = pil.resize((width, height))
    pixels = pil.load()
    rows = []
    for y in range(height):
        row = "".join(
            _CHARS[min(len(_CHARS) - 1, pixels[x, y] * len(_CHARS) // 256)]
            for x in range(width)
        )
        rows.append(row)
    return "\n".join(rows)
