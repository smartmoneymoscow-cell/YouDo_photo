def read_image(path: str, max_side: int = 512) -> np.ndarray:
    """Читает JPG/PNG/TIFF → numpy RGB. Memory-efficient."""
    import cv2
    import numpy as np

    # Try to load at reduced resolution directly (saves memory for large JPEGs)
    img = cv2.imread(path, cv2.IMREAD_REDUCED_COLOR_4)
    if img is None:
        raise FileNotFoundError(f"Не удалось прочитать: {path}")

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]

    if max(h, w) > max_side:
        scale = max_side / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)),
                         interpolation=cv2.INTER_AREA)

    return img
