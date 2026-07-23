def read_image(path: str, max_side: int = 1024) -> np.ndarray:
    """Читает JPG/PNG/TIFF → numpy RGB. Memory-efficient."""
    from PIL import Image
    import io

    # Use PIL with draft() for memory-efficient JPEG loading
    try:
        pil_img = Image.open(path)
    except Exception as e:
        raise FileNotFoundError(f"Не удалось прочитать: {path}")

    # For JPEG: use draft() to load at reduced resolution directly
    w, h = pil_img.size
    if max(w, h) > max_side:
        # draft() hints the decoder to load a reduced version
        if pil_img.format == 'JPEG':
            draft_side = max_side // 2  # load even smaller, then resize
            pil_img.draft('RGB', (draft_side, draft_side))
        pil_img = pil_img.convert('RGB')
        w2, h2 = pil_img.size
        if max(w2, h2) > max_side:
            scale = max_side / max(w2, h2)
            pil_img = pil_img.resize(
                (int(w2 * scale), int(h2 * scale)),
                Image.LANCZOS
            )
    else:
        pil_img = pil_img.convert('RGB')

    import numpy as np
    return np.array(pil_img)
