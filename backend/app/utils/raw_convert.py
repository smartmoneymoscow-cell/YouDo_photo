"""RAW/CR3 file conversion to usable image arrays."""

import rawpy
import numpy as np
from PIL import Image
import io


def raw_to_rgb(raw_bytes: bytes) -> np.ndarray:
    """Convert RAW bytes to RGB numpy array (16-bit)."""
    with rawpy.imread(io.BytesIO(raw_bytes)) as raw:
        rgb = raw.postprocess(
            use_camera_wb=True,
            half_size=False,
            no_auto_bright=False,
            output_bps=16,
        )
    return rgb


def raw_to_thumbnail(raw_bytes: bytes, max_size: int = 800) -> bytes:
    """Generate JPEG thumbnail from RAW for preview."""
    with rawpy.imread(io.BytesIO(raw_bytes)) as raw:
        rgb = raw.postprocess(
            use_camera_wb=True,
            half_size=True,
            no_auto_bright=False,
            output_bps=8,
        )

    img = Image.fromarray(rgb)
    img.thumbnail((max_size, max_size), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def rgb_to_jpeg(rgb_array: np.ndarray, quality: int = 90, max_side: int = None) -> bytes:
    """Convert RGB numpy array to JPEG bytes."""
    if rgb_array.dtype == np.uint16:
        img = Image.fromarray((rgb_array / 256).astype(np.uint8))
    else:
        img = Image.fromarray(rgb_array)

    if max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
