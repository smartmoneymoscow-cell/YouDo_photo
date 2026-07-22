"""Extract representative frames from video."""

import cv2
import numpy as np


def extract_key_frames(video_bytes: bytes, max_frames: int = 10) -> list[np.ndarray]:
    """Extract evenly spaced key frames from video bytes.

    Returns list of RGB numpy arrays.
    """
    # Write to temp file for OpenCV
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        temp_path = f.name

    try:
        cap = cv2.VideoCapture(temp_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        if total_frames == 0 or fps == 0:
            return []

        # Sample evenly spaced frames
        indices = np.linspace(0, total_frames - 1, max_frames, dtype=int)

        frames = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(frame_rgb)

        cap.release()
        return frames

    finally:
        os.unlink(temp_path)


def extract_frame_at(video_bytes: bytes, timestamp_sec: float) -> np.ndarray | None:
    """Extract single frame at specific timestamp."""
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        temp_path = f.name

    try:
        cap = cv2.VideoCapture(temp_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp_sec * 1000)
        ret, frame = cap.read()
        cap.release()

        if ret:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return None

    finally:
        os.unlink(temp_path)
