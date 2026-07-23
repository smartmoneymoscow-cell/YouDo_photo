"""YouDo Photo v2 — Backend API с реальным AI-отбором по эмбеддингам."""

import os
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.app.routes import upload, analyze, export
from backend.app.services.session import get_session

# ─── Конфиг ───
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

VID_EXT = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.wmv', '.flv', '.3gp'}

# ─── FastAPI ───
app = FastAPI(
    title="YouDo Photo API",
    description="AI-отбор интерьерных фотографий по сходству с эталоном",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API роутеры ───
app.include_router(upload.router, prefix="/api")
app.include_router(analyze.router, prefix="/api")
app.include_router(export.router, prefix="/api")


# ─── Видео загрузка + извлечение кадров ───
@app.post("/api/upload/video/{session_id}")
async def upload_video(
    session_id: str,
    files: list[UploadFile] = File(...),
    fps: float = 1.0,
    max_frames: int = 30,
):
    """Загружает видео и извлекает кадры через ffmpeg."""
    import subprocess

    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Сессия не найдена")

    video_dir = os.path.join(UPLOAD_DIR, session_id, "videos")
    frames_dir = session.photo_dir
    os.makedirs(video_dir, exist_ok=True)
    os.makedirs(frames_dir, exist_ok=True)

    saved_videos = []
    extracted_frames = []

    for f in files:
        ext = Path(f.filename).suffix.lower()
        if ext not in VID_EXT:
            continue

        dest = os.path.join(video_dir, f.filename)
        content = await f.read()
        with open(dest, "wb") as out:
            out.write(content)
        saved_videos.append(f.filename)

        basename = Path(f.filename).stem
        cmd = [
            "ffmpeg", "-i", dest,
            "-vf", f"fps={fps}",
            "-q:v", "2",
            "-frames:v", str(max_frames),
            os.path.join(frames_dir, f"{basename}_frame_%04d.jpg"),
            "-y", "-hide_banner", "-loglevel", "error",
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        except Exception as e:
            print(f"ffmpeg error: {e}")
            continue

        frames = sorted([
            os.path.join(frames_dir, fn)
            for fn in os.listdir(frames_dir)
            if fn.startswith(f"{basename}_frame_") and fn.endswith(".jpg")
        ])
        extracted_frames.extend(frames)
        for frame_path in frames:
            session.photo_files.append(frame_path)

    return {
        "saved_videos": saved_videos,
        "extracted_frames": len(extracted_frames),
        "total_photos": len(session.photo_files),
        "frames": [os.path.basename(f) for f in extracted_frames],
    }


# ─── Health ───
@app.get("/health")
async def health():
    return {"status": "ok"}


# ─── Фронтенд ───
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>YouDo Photo v2</h1><p>Frontend not found</p>")


css_dir = os.path.join(FRONTEND_DIR, "css")
js_dir = os.path.join(FRONTEND_DIR, "js")
if os.path.isdir(css_dir):
    app.mount("/css", StaticFiles(directory=css_dir), name="css")
if os.path.isdir(js_dir):
    app.mount("/js", StaticFiles(directory=js_dir), name="js")


if __name__ == "__main__":
    import uvicorn
    print("╔══════════════════════════════════════════╗")
    print("║    YouDo Photo v2 — AI-отбор (real)      ║")
    print("╚══════════════════════════════════════════╝")
    uvicorn.run(app, host="0.0.0.0", port=8000)
