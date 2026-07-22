"""YouDo Photo v2 — Самостоятельный сервер (без torch/rawpy для demo)."""

import os
import io
import uuid
import json
import zipfile
import time
import math
from pathlib import Path
from dataclasses import dataclass, field, asdict

import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ═══════════════════════════════════════════
#  Конфигурация
# ═══════════════════════════════════════════

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ═══════════════════════════════════════════
#  FastAPI
# ═══════════════════════════════════════════

app = FastAPI(title="YouDo Photo API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════
#  Сессии
# ═══════════════════════════════════════════

@dataclass
class Session:
    id: str
    ref_dir: str = ""
    photo_dir: str = ""
    ref_files: list = field(default_factory=list)
    photo_files: list = field(default_factory=list)
    results: list = field(default_factory=list)
    status: str = "created"

_sessions: dict[str, Session] = {}

def create_session() -> Session:
    sid = uuid.uuid4().hex[:12]
    ref_dir = os.path.join(UPLOAD_DIR, sid, "references")
    photo_dir = os.path.join(UPLOAD_DIR, sid, "photos")
    os.makedirs(ref_dir, exist_ok=True)
    os.makedirs(photo_dir, exist_ok=True)
    session = Session(id=sid, ref_dir=ref_dir, photo_dir=photo_dir)
    _sessions[sid] = session
    return session

# ═══════════════════════════════════════════
#  Анализ (демо-версия на numpy, без torch)
# ═══════════════════════════════════════════

RAW_EXT = {'.cr3', '.cr2', '.nef', '.arw', '.raf', '.rw2', '.dng', '.raw', '.orf', '.srw', '.pef'}
IMG_EXT = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp'}

def find_files(directory: str) -> list[str]:
    all_ext = RAW_EXT | IMG_EXT
    files = []
    for root, _, names in os.walk(directory):
        for f in sorted(names):
            if Path(f).suffix.lower() in all_ext:
                files.append(os.path.join(root, f))
    return files

def image_to_histogram_vector(path: str, bins: int = 64) -> np.ndarray:
    """
    Извлекает特征-вектор из изображения через цветовые гистограммы.
    Работает без torch — только numpy + PIL.
    Это ДЕМО-режим. Для продакшена нужен OpenCLIP/DINOv2.
    """
    from PIL import Image

    try:
        img = Image.open(path).convert('RGB')
    except Exception:
        # Для RAW файлов — заглушка (имя файла → хеш)
        h = hash(Path(path).name) % 10000
        rng = np.random.RandomState(h)
        return rng.randn(192).astype(np.float32)

    img = img.resize((128, 128))
    arr = np.array(img)

    # Цветовые гистограммы по каналам R, G, B
    vectors = []
    for ch in range(3):
        hist, _ = np.histogram(arr[:, :, ch], bins=bins, range=(0, 256))
        hist = hist.astype(np.float32)
        hist /= (hist.sum() + 1e-8)
        vectors.append(hist)

    # Дополнительно: средние значения по квадрантам
    h, w = arr.shape[:2]
    for qy in range(2):
        for qx in range(2):
            q = arr[qy*h//2:(qy+1)*h//2, qx*w//2:(qx+1)*w//2]
            vectors.append(q.mean(axis=(0, 1)).astype(np.float32) / 255.0)

    return np.concatenate(vectors)

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))

def analyze_photos(ref_dir: str, photo_dir: str, threshold: float = 0.75, top_k: int = 0) -> dict:
    t0 = time.time()

    ref_paths = find_files(ref_dir)
    photo_paths = find_files(photo_dir)

    # Исключаем эталоны
    ref_set = set(os.path.abspath(p) for p in ref_paths)
    photo_paths = [p for p in photo_paths if os.path.abspath(p) not in ref_set]

    if not ref_paths:
        return {"error": "Нет эталонов", "status": "error"}
    if not photo_paths:
        return {"error": "Нет фото", "status": "error"}

    # Эмбеддинги эталонов
    ref_vecs = [image_to_histogram_vector(p) for p in ref_paths]
    ref_mean = np.mean(ref_vecs, axis=0)
    ref_mean = ref_mean / (np.linalg.norm(ref_mean) + 1e-8)

    # Эмбеддинги фото + сравнение
    results = []
    for i, p in enumerate(photo_paths):
        vec = image_to_histogram_vector(p)
        score = cosine_sim(vec, ref_mean)
        results.append({
            "path": p,
            "score": round(score, 4),
            "rank": 0,
            "accepted": score >= threshold,
        })

    # Сортировка
    results.sort(key=lambda x: -x["score"])
    for i, r in enumerate(results):
        r["rank"] = i + 1

    if top_k > 0:
        results = results[:top_k]

    accepted = [r for r in results if r["accepted"]]
    elapsed = round(time.time() - t0, 1)

    return {
        "status": "ok",
        "elapsed_sec": elapsed,
        "model": "histogram_demo",
        "model_dim": 192,
        "threshold": threshold,
        "total": len(results),
        "accepted_count": len(accepted),
        "rejected_count": len(results) - len(accepted),
        "best_score": round(results[0]["score"], 4) if results else 0,
        "worst_score": round(results[-1]["score"], 4) if results else 0,
        "results": results,
        "accepted": accepted,
        "rejected": [r for r in results if not r["accepted"]],
    }

# ═══════════════════════════════════════════
#  API Endpoints
# ═══════════════════════════════════════════

@app.post("/api/session/create")
async def api_create_session():
    session = create_session()
    return {"session_id": session.id, "status": "created"}

@app.post("/api/upload/references/{session_id}")
async def upload_references(session_id: str, files: list[UploadFile] = File(...)):
    session = _sessions.get(session_id)
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
    return {"saved": saved, "total_refs": len(session.ref_files)}

@app.post("/api/upload/photos/{session_id}")
async def upload_photos(session_id: str, files: list[UploadFile] = File(...)):
    session = _sessions.get(session_id)
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

class AnalyzeRequest(BaseModel):
    model: str = "histogram_demo"
    threshold: float = 0.75
    top_k: int = 0
    ref_method: str = "max"
    max_side: int = 1024

@app.post("/api/analyze/{session_id}")
async def api_analyze(session_id: str, req: AnalyzeRequest):
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Сессия не найдена")
    if not session.ref_files:
        raise HTTPException(400, "Нет эталонов")
    if not session.photo_files:
        raise HTTPException(400, "Нет фотографий")

    result = analyze_photos(
        ref_dir=session.ref_dir,
        photo_dir=session.photo_dir,
        threshold=req.threshold,
        top_k=req.top_k if req.top_k else 0,
    )

    if result.get("status") == "error":
        raise HTTPException(400, result["error"])

    session.results = result.get("results", [])
    session.status = "analyzed"
    return result

@app.post("/api/export/{session_id}/zip")
async def api_export_zip(session_id: str):
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Сессия не найдена")
    if session.status != "analyzed":
        raise HTTPException(400, "Анализ не выполнен")

    accepted = [r for r in session.results if r.get("accepted")]
    if not accepted:
        raise HTTPException(400, "Нет принятых файлов")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        meta = f"YouDo Photo Export\nПринято: {len(accepted)} из {len(session.results)}\n\n"
        for r in accepted:
            meta += f"  #{r['rank']} {r['score']:.2%} {Path(r['path']).name}\n"
        zf.writestr("README.txt", meta)
        for r in accepted:
            if os.path.exists(r["path"]):
                zf.write(r["path"], f"accepted/{Path(r['path']).name}")

    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=youdo_photo_{session_id}.zip"},
    )

@app.get("/api/export/{session_id}/json")
async def api_export_json(session_id: str):
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Сессия не найдена")
    content = json.dumps({
        "session_id": session.id,
        "total": len(session.results),
        "accepted": len([r for r in session.results if r.get("accepted")]),
        "results": session.results,
    }, ensure_ascii=False, indent=2)
    return StreamingResponse(
        io.BytesIO(content.encode()), media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=results_{session_id}.json"},
    )

@app.get("/api/models")
async def api_models():
    return {
        "histogram_demo": {"dim": 192, "description": "Демо: цветовые гистограммы (numpy)", "fast": True},
        "note": "Для полной модели установите torch + open-clip-torch",
    }

# ═══════════════════════════════════════════
#  Фронтенд
# ═══════════════════════════════════════════

# Раздаём index.html на /
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>YouDo Photo v2</h1><p>Frontend not found</p>")

# Раздаём статику
app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")

# ═══════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    print("╔══════════════════════════════════════════╗")
    print("║       YouDo Photo v2 — AI-отбор фото     ║")
    print("╚══════════════════════════════════════════╝")
    print("  http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
