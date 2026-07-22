"""Color correction to match reference images/video frames."""

import cv2
import numpy as np
from PIL import Image
import io


def extract_color_stats(img_array: np.ndarray) -> dict:
    """Extract mean/std color statistics from an image."""
    # Convert to LAB for perceptual uniformity
    lab = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB).astype(np.float32)
    return {
        "mean": lab.mean(axis=(0, 1)),
        "std": lab.std(axis=(0, 1)),
    }


def match_color(source: np.ndarray, reference: np.ndarray, intensity: float = 1.0) -> np.ndarray:
    """Transfer color statistics from reference to source image.

    Uses Reinhard's method in LAB color space.
    intensity: 0.0 = no change, 1.0 = full match
    """
    src_lab = cv2.cvtColor(source, cv2.COLOR_RGB2LAB).astype(np.float32)
    ref_lab = cv2.cvtColor(reference, cv2.COLOR_RGB2LAB).astype(np.float32)

    src_mean = src_lab.mean(axis=(0, 1))
    src_std = src_lab.std(axis=(0, 1))
    ref_mean = ref_lab.mean(axis=(0, 1))
    ref_std = ref_lab.std(axis=(0, 1))

    # Avoid division by zero
    src_std = np.maximum(src_std, 1e-6)

    # Reinhard transfer
    result = (src_lab - src_mean) * (ref_std / src_std) + ref_mean

    # Apply intensity
    result = src_lab + (result - src_lab) * intensity

    # Clip to valid range
    result = np.clip(result, 0, 255).astype(np.uint8)

    return cv2.cvtColor(result, cv2.COLOR_LAB2RGB)


def match_color_multi(source: np.ndarray, references: list[np.ndarray], intensity: float = 1.0) -> np.ndarray:
    """Match color against multiple reference images (average their stats)."""
    if not references:
        return source

    ref_means = []
    ref_stds = []

    for ref in references:
        stats = extract_color_stats(ref)
        ref_means.append(stats["mean"])
        ref_stds.append(stats["std"])

    # Average reference stats
    avg_mean = np.mean(ref_means, axis=0)
    avg_std = np.mean(ref_stds, axis=0)

    src_lab = cv2.cvtColor(source, cv2.COLOR_RGB2LAB).astype(np.float32)
    src_mean = src_lab.mean(axis=(0, 1))
    src_std = np.maximum(src_lab.std(axis=(0, 1)), 1e-6)

    result = (src_lab - src_mean) * (avg_std / src_std) + avg_mean
    result = src_lab + (result - src_lab) * intensity
    result = np.clip(result, 0, 255).astype(np.uint8)

    return cv2.cvtColor(result, cv2.COLOR_LAB2RGB)
