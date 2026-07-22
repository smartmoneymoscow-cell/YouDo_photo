"""Upload routes — handle file uploads to R2."""

from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from app.storage import create_session, upload_file, list_session_files
from app.config import MAX_FILE_SIZE_MB, MAX_FILES_PER_SESSION

router = APIRouter(prefix="/api/upload", tags=["upload"])

ALLOWED_RAW = {".cr3", ".cr2", ".nef", ".arw", ".raf", ".rw2", ".dng", ".raw"}
ALLOWED_IMG = {".jpg", ".jpeg"}
ALLOWED_VIDEO = {".mp4", ".mov", ".avi", ".mkv"}


def validate_extension(filename: str, allowed: set) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed:
        raise HTTPException(400, f"Неподдерживаемый формат: {ext}. Допустимы: {allowed}")
    return ext


@router.post("/session")
async def create_new_session():
    """Create a new upload session."""
    session_id = create_session()
    return {"session_id": session_id}


@router.post("/{session_id}/raw")
async def upload_raw(session_id: str, files: List[UploadFile] = File(...)):
    """Upload RAW/CR3 files."""
    if len(files) > MAX_FILES_PER_SESSION:
        raise HTTPException(400, f"Слишком много файлов. Максимум: {MAX_FILES_PER_SESSION}")

    uploaded = []
    for f in files:
        ext = validate_extension(f.filename, ALLOWED_RAW)
        data = await f.read()
        if len(data) > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(400, f"Файл {f.filename} слишком большой (>{MAX_FILE_SIZE_MB} МБ)")

        key = upload_file(session_id, "raw", f.filename, data)
        uploaded.append({"filename": f.filename, "key": key, "size": len(data)})

    return {"uploaded": uploaded, "count": len(uploaded)}


@router.post("/{session_id}/references")
async def upload_references(session_id: str, files: List[UploadFile] = File(...)):
    """Upload JPG reference images."""
    if len(files) > 20:
        raise HTTPException(400, "Максимум 20 эталонов")

    uploaded = []
    for f in files:
        ext = validate_extension(f.filename, ALLOWED_IMG)
        data = await f.read()
        key = upload_file(session_id, "references", f.filename, data)
        uploaded.append({"filename": f.filename, "key": key, "size": len(data)})

    return {"uploaded": uploaded, "count": len(uploaded)}


@router.post("/{session_id}/video")
async def upload_video(session_id: str, file: UploadFile = File(...)):
    """Upload apartment video."""
    ext = validate_extension(file.filename, ALLOWED_VIDEO)
    data = await file.read()
    if len(data) > 500 * 1024 * 1024:  # 500MB limit
        raise HTTPException(400, "Видео слишком большое (макс 500 МБ)")

    key = upload_file(session_id, "video", file.filename, data)
    return {"filename": file.filename, "key": key, "size": len(data)}


@router.get("/{session_id}/files")
async def list_files(session_id: str):
    """List all files in a session."""
    raw = list_session_files(session_id, "raw")
    refs = list_session_files(session_id, "references")
    video = list_session_files(session_id, "video")
    processed = list_session_files(session_id, "processed")

    return {
        "raw": raw,
        "references": refs,
        "video": video,
        "processed": processed,
    }
