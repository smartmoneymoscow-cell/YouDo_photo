"""Processing routes — RAW conversion, scoring, color correction."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from app.storage import download_file, upload_file, list_session_files
from app.utils.raw_convert import raw_to_rgb, raw_to_thumbnail, rgb_to_jpeg
from app.utils.score import score_image
from app.utils.color_match import match_color_multi
from app.utils.video_extract import extract_key_frames
import numpy as np
import cv2
import io
import zipfile

router = APIRouter(prefix="/api/process", tags=["process"])


class ColorParams(BaseModel):
    source: str = "jpg"  # jpg | video | both
    style: str = "reference"  # neutral | reference | video
    intensity: float = 0.7


class ExportParams(BaseModel):
    format: str = "jpg"
    quality: int = 90
    max_side: Optional[int] = None


@router.post("/{session_id}/thumbnails")
async def generate_thumbnails(session_id: str):
    """Generate thumbnails for all RAW files."""
    raw_files = list_session_files(session_id, "raw")
    if not raw_files:
        raise HTTPException(404, "Нет RAW файлов в сессии")

    results = []
    for f in raw_files:
        raw_data = download_file(f["key"])
        thumb_data = raw_to_thumbnail(raw_data)
        fname = f["key"].rsplit("/", 1)[-1]
        thumb_name = fname.rsplit(".", 1)[0] + "_thumb.jpg"
        upload_file(session_id, "thumbnails", thumb_name, thumb_data)
        results.append({"filename": fname, "thumbnail": thumb_name})

    return {"thumbnails": results, "count": len(results)}


@router.post("/{session_id}/score")
async def score_files(session_id: str):
    """Score all RAW files for quality."""
    raw_files = list_session_files(session_id, "raw")
    if not raw_files:
        raise HTTPException(404, "Нет RAW файлов")

    results = []
    for f in raw_files:
        raw_data = download_file(f["key"])
        # Use thumbnail for faster scoring
        thumb = raw_to_thumbnail(raw_data)
        scores = score_image(thumb)
        fname = f["key"].rsplit("/", 1)[-1]
        results.append({
            "filename": fname,
            "key": f["key"],
            "scores": scores,
        })

    # Sort by total score descending
    results.sort(key=lambda x: x["scores"]["total"], reverse=True)

    return {"scored": results, "count": len(results)}


@router.post("/{session_id}/color-correct")
async def color_correct(session_id: str, params: ColorParams):
    """Apply color correction to RAW files based on references."""
    raw_files = list_session_files(session_id, "raw")
    ref_files = list_session_files(session_id, "references")

    if not raw_files:
        raise HTTPException(404, "Нет RAW файлов")
    if not ref_files and params.style != "neutral":
        raise HTTPException(404, "Нет JPG-эталонов для цветокоррекции")

    # Load references
    ref_images = []
    if ref_files:
        for rf in ref_files:
            ref_data = download_file(rf["key"])
            nparr = np.frombuffer(ref_data, np.uint8)
            ref_img = cv2.imdecode(nparr, cv2.COLOR_BGR2RGB)
            if ref_img is not None:
                ref_images.append(cv2.cvtColor(ref_img, cv2.COLOR_BGR2RGB))

    # Load video frames if needed
    video_frames = []
    if params.source in ("video", "both"):
        vid_files = list_session_files(session_id, "video")
        if vid_files:
            vid_data = download_file(vid_files[0]["key"])
            video_frames = extract_key_frames(vid_data, max_frames=10)

    all_refs = ref_images + video_frames

    results = []
    for f in raw_files:
        raw_data = download_file(f["key"])
        rgb = raw_to_rgb(raw_data)

        if params.style != "neutral" and all_refs:
            corrected = match_color_multi(rgb, all_refs, params.intensity)
        else:
            corrected = rgb

        fname = f["key"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
        out_name = f"{fname}_corrected.jpg"
        jpeg_data = rgb_to_jpeg(corrected, quality=90)
        upload_file(session_id, "processed", out_name, jpeg_data)
        results.append({"filename": out_name, "key": f"sessions/{session_id}/processed/{out_name}"})

    return {"processed": results, "count": len(results)}


@router.post("/{session_id}/export")
async def export_zip(session_id: str, params: ExportParams):
    """Export accepted processed images as ZIP."""
    processed = list_session_files(session_id, "processed")
    if not processed:
        raise HTTPException(404, "Нет обработанных файлов")

    # Create ZIP in memory
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in processed:
            data = download_file(f["key"])
            fname = f["key"].rsplit("/", 1)[-1]
            zf.writestr(fname, data)

    zip_buf.seek(0)

    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={session_id}_photos.zip"},
    )
