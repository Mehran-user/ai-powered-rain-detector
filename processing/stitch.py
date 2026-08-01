import logging

import cv2
import numpy as np

logger = logging.getLogger("rain_logger")


def stitch_horizontal(images, separator_width=20):
    if not images:
        raise ValueError("No images provided to stitch.")
    height = max(img.shape[0] for img in images)
    resized = []
    for img in images:
        current_height, current_width = img.shape[:2]
        if current_height != height:
            scale = height / current_height
            new_width = max(1, int(round(current_width * scale)))
            resized.append(cv2.resize(img, (new_width, height)))
        else:
            resized.append(img)
    separator = np.zeros((height, separator_width, 3), dtype=np.uint8)
    parts = []
    for index, img in enumerate(resized):
        if index:
            parts.append(separator)
        parts.append(img)
    stitched = np.hstack(parts)
    logger.info("Images stitched.")
    return stitched
