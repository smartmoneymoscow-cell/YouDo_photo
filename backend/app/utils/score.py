"""Image quality scoring for moderation."""

import cv2
import numpy as np
from PIL import Image
import io


def calculate_sharpness(img_array: np.ndarray) -> float:
    """Score sharpness using Laplacian variance. Returns 0-100."""
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array

    # Downscale for speed
    h, w = gray.shape[:2]
    if max(h, w) > 1000:
        scale = 1000 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale)

    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    variance = laplacian.var()

    # Map to 0-100 (empirical thresholds)
    score = min(100, (variance / 500) * 100)
    return round(score, 1)


def calculate_exposure(img_array: np.ndarray) -> float:
    """Score exposure quality. Penalizes over/underexposure. Returns 0-100."""
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array

    # Histogram analysis
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    total = hist.sum()

    # Percentage of pixels in "good" range (20-235)
    good_range = hist[20:235].sum()
    good_ratio = good_range / total

    # Penalize clipping
    shadows_clip = hist[:10].sum() / total
    highlights_clip = hist[245:].sum() / total
    clipping_penalty = (shadows_clip + highlights_clip) * 100

    score = (good_ratio * 100) - clipping_penalty
    return round(max(0, min(100, score)), 1)


def detect_blur(img_array: np.ndarray) -> bool:
    """Detect if image is blurry (motion blur or out of focus)."""
    sharpness = calculate_sharpness(img_array)
    return sharpness < 15  # threshold


def score_image(img_bytes: bytes) -> dict:
    """Full scoring pipeline. Returns dict with scores."""
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return {"sharpness": 0, "exposure": 0, "total": 0, "is_blurry": True}

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    sharpness = calculate_sharpness(img_rgb)
    exposure = calculate_exposure(img_rgb)

    # Weighted total
    total = sharpness * 0.5 + exposure * 0.5

    return {
        "sharpness": sharpness,
        "exposure": exposure,
        "total": round(total, 1),
        "is_blurry": detect_blur(img_rgb),
    }
