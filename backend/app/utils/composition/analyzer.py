"""Composition analysis for interior photography.

Based on photo-assistant (spirit0707) composition module.
Adapted for interior/architectural photography.
"""

import cv2
import numpy as np


def detect_lines(image: np.ndarray) -> list:
    """Detect dominant lines using Hough transform (for interiors)."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                            minLineLength=100, maxLineGap=10)
    if lines is None:
        return []
    return lines.tolist()


def check_horizon_level(image: np.ndarray) -> dict:
    """Check if horizon/vertical lines are level.

    Returns dict with angle and score.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                            minLineLength=100, maxLineGap=10)

    if lines is None:
        return {"angle": 0, "score": 100, "tip": None}

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        # Focus on near-horizontal lines
        if abs(angle) < 30:
            angles.append(angle)

    if not angles:
        return {"angle": 0, "score": 100, "tip": None}

    median_angle = np.median(angles)
    deviation = abs(median_angle)
    score = max(0, 100 - deviation * 10)

    tip = None
    if deviation > 2:
        tip = f"Горизонт завален на {median_angle:.1f}°. Рекомендуется выпрямить."

    return {"angle": round(median_angle, 2), "score": round(score, 1), "tip": tip}


def rule_of_thirds_score(image: np.ndarray) -> dict:
    """Evaluate composition by rule of thirds.

    Detects salient regions and checks if they align with thirds grid.
    """
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

    # Find salient points using goodFeaturesToTrack
    corners = cv2.goodFeaturesToTrack(gray, maxCorners=20, qualityLevel=0.01,
                                       minDistance=50)
    if corners is None or len(corners) == 0:
        return {"score": 50, "tip": "Не удалось определить ключевые точки композиции."}

    # Grid lines at 1/3 and 2/3
    grid_x = [w / 3, 2 * w / 3]
    grid_y = [h / 3, 2 * h / 3]

    # Check how close corners are to grid intersections
    threshold = min(w, h) * 0.08  # 8% tolerance
    aligned = 0

    for corner in corners:
        cx, cy = corner[0]
        for gx in grid_x:
            for gy in grid_y:
                dist = np.sqrt((cx - gx) ** 2 + (cy - gy) ** 2)
                if dist < threshold:
                    aligned += 1
                    break

    ratio = aligned / len(corners)
    score = min(100, ratio * 200)  # scale up

    tip = None
    if score < 40:
        tip = "Объекты не совпадают с точками силы (правило третей). Попробуйте сдвинуть камеру."

    return {"score": round(score, 1), "tip": tip}


def analyze_symmetry(image: np.ndarray) -> dict:
    """Check vertical symmetry (useful for interior/facade shots)."""
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

    left = gray[:, :w // 2]
    right = cv2.flip(gray[:, w - w // 2:], 1)

    # Resize to match
    min_w = min(left.shape[1], right.shape[1])
    left = left[:, :min_w]
    right = right[:, :min_w]

    diff = cv2.absdiff(left, right)
    symmetry = 100 - (np.mean(diff) / 255 * 100)

    tip = None
    if symmetry < 60:
        tip = "Кадр не симметричен. Для интерьеров это может быть критично."

    return {"score": round(symmetry, 1), "tip": tip}


def analyze_composition(image: np.ndarray) -> dict:
    """Full composition analysis pipeline for interior photos."""
    horizon = check_horizon_level(image)
    thirds = rule_of_thirds_score(image)
    symm = analyze_symmetry(image)

    # Weighted average
    total = (
        horizon["score"] * 0.4 +
        thirds["score"] * 0.35 +
        symm["score"] * 0.25
    )

    tips = []
    for result in [horizon, thirds, symm]:
        if result.get("tip"):
            tips.append(result["tip"])

    return {
        "total": round(total, 1),
        "horizon": horizon,
        "thirds": thirds,
        "symmetry": symm,
        "tips": tips,
    }
