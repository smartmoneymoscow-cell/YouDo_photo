"""API: загрузка файлов с конвертацией RAW→JPG."""

import os
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.app.services.session import create_session, get_session

router = APIRouter(tags=["upload"])

RAW_EXT = {'.cr3', '.cr2', '.nef', '.arw', '.raf', '.rw2', '.dng', '.raw'}


def _convert_raw_to_jpg(src_path: str, dst_path: str, max_side: int = 1024) -> bool:
    """Конвертирует RAW файл в JPG. Возвращает True при успехе."""
    try:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        from core.raw_reader import read_image, is_raw
        from PIL import Image

        if not is_raw(src_path):
            return False

        img_np = read_image(src_path, max_side=max_side)
        img_pil = Image.fromarray(img_np)
        img_pil.save(dst_path, 'JPEG', quality=92)
        return True
    except Exception as e:
        print(f"RAW convert error for {src_path}: {e}")
        return False


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
    """Загружает фотографии. RAW/CR3 автоматически конвертируются в JPG."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Сессия не найдена")

    saved = []
    converted = []
    for f in files:
        ext = Path(f.filename).suffix.lower()
        content = await f.read()

        # Сохраняем оригинал
        src_path = os.path.join(session.photo_dir, f.filename)
        with open(src_path, "wb") as out:
            out.write(content)

        # Если RAW — конвертируем в JPG
        if ext in RAW_EXT:
            jpg_name = Path(f.filename).stem + ".jpg"
            jpg_path = os.path.join(session.photo_dir, jpg_name)
            if _convert_raw_to_jpg(src_path, jpg_path):
                # Удаляем оригинал RAW — он не нужен для отображения
                try:
                    os.remove(src_path)
                except OSError:
                    pass
                session.photo_files.append(jpg_path)
                converted.append(f"{f.filename} → {jpg_name}")
                saved.append(jpg_name)
            else:
                # Конвертация не удалась — сохраняем оригинал
                session.photo_files.append(src_path)
                saved.append(f.filename)
        else:
            session.photo_files.append(src_path)
            saved.append(f.filename)

    return {
        "saved": saved,
        "converted": converted,
        "total_photos": len(session.photo_files),
    }


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
