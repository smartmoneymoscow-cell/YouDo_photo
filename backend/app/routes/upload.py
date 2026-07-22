"""API: загрузка файлов."""

import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.session import create_session, get_session

router = APIRouter(tags=["upload"])


@router.post("/session/create")
async def api_create_session():
    """Создаёт новую сессию обработки."""
    session = create_session()
    return {"session_id": session.id, "status": "created"}


@router.post("/upload/references/{session_id}")
async def upload_references(session_id: str, files: list[UploadFile] = File(...)):
    """Загружает эталонные JPG."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Сессия не найдена")

    saved = []
    for f in files:
        dest = os.path.join(session.ref_dir, f.filename)
        content = await f.read()
        with open(dest, "wb") as out:
            out.write(content)
        saved.append(f.filename)
        session.ref_files.append(dest)

    session.status = "uploaded"
    return {"saved": saved, "total_refs": len(session.ref_files)}


@router.post("/upload/photos/{session_id}")
async def upload_photos(session_id: str, files: list[UploadFile] = File(...)):
    """Загружает CR3/RAW фотографии."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Сессия не найдена")

    saved = []
    for f in files:
        dest = os.path.join(session.photo_dir, f.filename)
        content = await f.read()
        with open(dest, "wb") as out:
            out.write(content)
        saved.append(f.filename)
        session.photo_files.append(dest)

    return {"saved": saved, "total_photos": len(session.photo_files)}


@router.get("/upload/status/{session_id}")
async def upload_status(session_id: str):
    """Статус загрузки файлов."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Сессия не найдена")

    return {
        "session_id": session.id,
        "status": session.status,
        "ref_count": len(session.ref_files),
        "photo_count": len(session.photo_files),
        "ref_files": [os.path.basename(f) for f in session.ref_files],
        "photo_files": [os.path.basename(f) for f in session.photo_files],
    }
