"""Image quality scoring for moderation.

Includes sharpness, exposure, blur detection, and composition analysis.
"""

import cv2
import numpy as np
from .composition.analyzer import analyze_composition


def calculate_sharpness(img_array: np.ndarray) -> float:
    """Score sharpness using Laplacian variance. Returns 0-100."""
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array

    h, w = gray.shape[:2]
    if max(h, w) > 1000:
        scale = 1000 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale)

    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    variance = laplacian.var()

    score = min(100, (variance / 500) * 100)
    return round(score, 1)


def calculate_exposure(img_array: np.ndarray) -> float:
    """Score exposure quality. Returns 0-100."""
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array

    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    total = hist.sum()

    good_range = hist[20:235].sum()
    good_ratio = good_range / total

    shadows_clip = hist[:10].sum() / total
    highlights_clip = hist[245:].sum() / total
    clipping_penalty = (shadows_clip + highlights_clip) * 100

    score = (good_ratio * 100) - clipping_penalty
    return round(max(0, min(100, score)), 1)


def detect_blur(img_array: np.ndarray) -> dict:
    """Detect blur. Returns dict with is_blur flag and sharpness value."""
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array

    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    is_blur = laplacian_var < 100

    return {
        "is_blurry": is_blur,
        "sharpness_value": round(laplacian_var, 1),
    }


def score_image(img_bytes: bytes) -> dict:
    """Full scoring pipeline. Returns dict with all scores."""
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return {
            "sharpness": 0,
            "exposure": 0,
            "composition": 0,
            "total": 0,
            "is_blurry": True,
            "tips": ["Не удалось загрузить изображение"],
        }

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    sharpness = calculate_sharpness(img_rgb)
    exposure = calculate_exposure(img_rgb)
    blur = detect_blur(img_rgb)

    # Composition analysis
    comp = analyze_composition(img)

    # Weighted total
    total = (
        sharpness * 0.35 +
        exposure * 0.25 +
        comp["total"] * 0.2 +
        (0 if blur["is_blurry"] else 20)
    )

    tips = []
    if blur["is_blurry"]:
        tips.append("Изображение размыто. Проверьте фокус.")
    if sharpness < 30:
        tips.append("Низкая резкость. Возможно, дрожание камеры.")
    if exposure < 40:
        tips.append("Проблемы с экспозицией. Слишком тёмное или светлое.")
    tips.extend(comp.get("tips", []))

    return {
        "sharpness": sharpness,
        "exposure": exposure,
        "composition": comp["total"],
        "total": round(min(100, total), 1),
        "is_blurry": blur["is_blurry"],
        "tips": tips,
    }
