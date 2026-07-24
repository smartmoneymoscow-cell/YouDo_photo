"""API: загрузка файлов с конвертацией RAW→JPG."""

import os
import re
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.app.services.session import create_session, get_session

router = APIRouter(tags=["upload"])

RAW_EXT = {'.cr3', '.cr2', '.nef', '.arw', '.raf', '.rw2', '.dng', '.raw'}

# Макс. размер файла — 100MB
MAX_FILE_SIZE = 100 * 1024 * 1024


def _sanitize_filename(name: str) -> str:
    """Убирает path traversal и опасные символы из имени файла."""
    # Только basename
    name = os.path.basename(name)
    # Убираем всё кроме букв, цифр, точек, дефисов, подчёркиваний
    name = re.sub(r'[^\w.\-]', '_', name)
    # Не начинается с точки (скрытые файлы)
    if name.startswith('.'):
        name = '_' + name
    return name or 'unnamed'


def _unique_path(directory: str, filename: str) -> str:
    """Генерирует уникальный путь, если файл с таким именем уже существует."""
    dest = os.path.join(directory, filename)
    if not os.path.exists(dest):
        return dest
    stem = Path(filename).stem
    ext = Path(filename).suffix
    counter = 1
    while True:
        new_name = f"{stem}_{counter}{ext}"
        dest = os.path.join(directory, new_name)
        if not os.path.exists(dest):
            return dest
        counter += 1


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


async def _read_upload_file(f: UploadFile) -> bytes:
    """Читает файл по частям, проверяя размер."""
    content = bytearray()
    chunk_size = 1024 * 1024  # 1MB
    while True:
        chunk = await f.read(chunk_size)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(413, f"Файл {f.filename} слишком большой (макс. 100MB)")
    return bytes(content)


@router.post("/upload/references/{session_id}")
async def upload_references(session_id: str, files: list[UploadFile] = File(...)):
    """Загружает эталонные JPG."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Сессия не найдена")

    saved = []
    for f in files:
        safe_name = _sanitize_filename(f.filename)
        content = await _read_upload_file(f)
        dest = _unique_path(session.ref_dir, safe_name)
        with open(dest, "wb") as out:
            out.write(content)
        saved.append(os.path.basename(dest))
        session.ref_files.append(dest)

    session.status = "uploaded"
    session.save()
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
        safe_name = _sanitize_filename(f.filename)
        ext = Path(safe_name).suffix.lower()
        content = await _read_upload_file(f)

        # Сохраняем оригинал с уникальным именем
        src_path = _unique_path(session.photo_dir, safe_name)
        with open(src_path, "wb") as out:
            out.write(content)

        # Если RAW — конвертируем в JPG
        if ext in RAW_EXT:
            jpg_name = Path(src_path).stem + ".jpg"
            jpg_path = _unique_path(session.photo_dir, jpg_name)
            if _convert_raw_to_jpg(src_path, jpg_path):
                # Удаляем оригинал RAW — он не нужен для отображения
                try:
                    os.remove(src_path)
                except OSError:
                    pass
                session.photo_files.append(jpg_path)
                converted.append(f"{safe_name} → {os.path.basename(jpg_path)}")
                saved.append(os.path.basename(jpg_path))
            else:
                # Конвертация не удалась — сохраняем оригинал
                session.photo_files.append(src_path)
                saved.append(os.path.basename(src_path))
        else:
            session.photo_files.append(src_path)
            saved.append(os.path.basename(src_path))

    session.save()
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
