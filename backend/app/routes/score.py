"""Scoring API endpoint — sends images for AI quality assessment."""

from fastapi import APIRouter, UploadFile, File, HTTPException
from app.utils.score import score_image
from app.utils.raw_convert import raw_to_rgb, raw_to_thumbnail
import numpy as np

router = APIRouter(prefix="/api/score", tags=["score"])


@router.post("/")
async def score_upload(file: UploadFile = File(...)):
    """Score a single image file (JPG/PNG or RAW)."""
    content = await file.read()

    # If RAW, convert to RGB first
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    raw_exts = {"cr3", "cr2", "nef", "arw", "raf", "rw2", "dng", "raw", "orf", "srw", "pef"}

    if ext in raw_exts:
        try:
            rgb = raw_to_rgb(content)
            # Convert to bytes for scoring
            from PIL import Image
            import io
            img = Image.fromarray(rgb if rgb.dtype == np.uint8 else (rgb / 256).astype(np.uint8))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=95)
            content = buf.getvalue()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"RAW conversion failed: {e}")

    try:
        result = score_image(content)
        return {
            "filename": file.filename,
            "scores": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring failed: {e}")


@router.post("/batch")
async def score_batch(files: list[UploadFile] = File(...)):
    """Score multiple images at once."""
    results = []
    for file in files:
        content = await file.read()

        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        raw_exts = {"cr3", "cr2", "nef", "arw", "raf", "rw2", "dng", "raw", "orf", "srw", "pef"}

        if ext in raw_exts:
            try:
                rgb = raw_to_rgb(content)
                from PIL import Image
                import io
                img = Image.fromarray(rgb if rgb.dtype == np.uint8 else (rgb / 256).astype(np.uint8))
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=95)
                content = buf.getvalue()
            except Exception as e:
                results.append({"filename": file.filename, "error": str(e)})
                continue

        try:
            result = score_image(content)
            results.append({"filename": file.filename, "scores": result})
        except Exception as e:
            results.append({"filename": file.filename, "error": str(e)})

    return {"results": results}
