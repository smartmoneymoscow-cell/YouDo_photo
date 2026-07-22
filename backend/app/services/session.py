"""Сервис: хранение загруженных файлов и сессий."""

import os
import uuid
import shutil
from pathlib import Path
from dataclasses import dataclass, field

# Директория для загрузок
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")


@dataclass
class Session:
    """Сессия обработки — один набор загруженных файлов."""
    id: str
    ref_dir: str = ""
    photo_dir: str = ""
    ref_files: list = field(default_factory=list)
    photo_files: list = field(default_factory=list)
    results: list = field(default_factory=list)
    status: str = "created"  # created | uploaded | analyzed | exported


# In-memory хранилище сессий
_sessions: dict[str, Session] = {}


def create_session() -> Session:
    """Создаёт новую сессию с директориями."""
    sid = uuid.uuid4().hex[:12]
    session_dir = os.path.join(UPLOAD_DIR, sid)
    ref_dir = os.path.join(session_dir, "references")
    photo_dir = os.path.join(session_dir, "photos")

    os.makedirs(ref_dir, exist_ok=True)
    os.makedirs(photo_dir, exist_ok=True)

    session = Session(id=sid, ref_dir=ref_dir, photo_dir=photo_dir)
    _sessions[sid] = session
    return session


def get_session(sid: str) -> Session | None:
    return _sessions.get(sid)


def list_sessions() -> list[Session]:
    return list(_sessions.values())


def cleanup_session(sid: str):
    """Удаляет сессию и её файлы."""
    session = _sessions.pop(sid, None)
    if session:
        session_dir = os.path.join(UPLOAD_DIR, sid)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
