"""Сервис: хранение загруженных файлов и сессий с JSON-персистентностью."""

import os
import uuid
import json
import shutil
from pathlib import Path
from dataclasses import dataclass, field, asdict

# Директория для загрузок
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "uploads"))
# Директория для метаданных сессий
SESSIONS_DIR = os.path.join(UPLOAD_DIR, ".sessions")


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

    def save(self):
        """Сохраняет метаданные сессии на диск."""
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        meta_path = os.path.join(SESSIONS_DIR, f"{self.id}.json")
        data = {
            "id": self.id,
            "ref_dir": self.ref_dir,
            "photo_dir": self.photo_dir,
            "ref_files": self.ref_files,
            "photo_files": self.photo_files,
            "results": self.results,
            "status": self.status,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)


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
    session.save()
    return session


def get_session(sid: str) -> Session | None:
    """Получает сессию — из памяти или с диска."""
    if sid in _sessions:
        return _sessions[sid]

    # Пробуем загрузить с диска
    meta_path = os.path.join(SESSIONS_DIR, f"{sid}.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            session = Session(
                id=data["id"],
                ref_dir=data.get("ref_dir", ""),
                photo_dir=data.get("photo_dir", ""),
                ref_files=data.get("ref_files", []),
                photo_files=data.get("photo_files", []),
                results=data.get("results", []),
                status=data.get("status", "created"),
            )
            _sessions[sid] = session
            return session
        except Exception as e:
            print(f"[Session] Failed to load {sid}: {e}")

    return None


def list_sessions() -> list[Session]:
    return list(_sessions.values())


def cleanup_session(sid: str):
    """Удаляет сессию и её файлы."""
    session = _sessions.pop(sid, None)
    if session:
        session_dir = os.path.join(UPLOAD_DIR, sid)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
    # Удаляем метаданные
    meta_path = os.path.join(SESSIONS_DIR, f"{sid}.json")
    if os.path.exists(meta_path):
        os.remove(meta_path)
