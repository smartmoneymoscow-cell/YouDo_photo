"""API: экспорт результатов."""

import os
import io
import zipfile
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from backend.app.services.session import get_session

router = APIRouter(tags=["export"])


class ExportRequest(BaseModel):
    format: str = Field(default="jpg", description="Формат: jpg/webp/png")
    quality: int = Field(default=90, ge=1, le=100, description="Качество JPG")
    include_rejected: bool = Field(default=False, description="Включить отклонённые")


@router.post("/export/{session_id}/zip")
async def api_export_zip(session_id: str, req: ExportRequest):
    """
    Экспортирует принятые фотографии в ZIP-архив.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Сессия не найдена")

    if session.status != "analyzed":
        raise HTTPException(400, "Анализ ещё не выполнен")

    # Фильтруем по статусу
    accepted = [r for r in session.results if r.get("accepted")]
    if req.include_rejected:
        files_to_export = session.results
    else:
        files_to_export = accepted

    if not files_to_export:
        raise HTTPException(400, "Нет файлов для экспорта")

    # Создаём ZIP в памяти
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Метаданные
        meta = f"YouDo Photo Export\nФормат: {req.format}\nКачество: {req.quality}\n"
        meta += f"Принято: {len(accepted)} из {len(session.results)}\n\n"
        meta += "Принятые кадры:\n"
        for r in accepted:
            meta += f"  #{r['rank']} {r['score']:.2%} {Path(r['path']).name}\n"
        zf.writestr("README.txt", meta)

        # Файлы
        for r in files_to_export:
            src = r["path"]
            if os.path.exists(src):
                name = Path(src).name
                if r.get("accepted"):
                    zf.write(src, f"accepted/{name}")
                else:
                    zf.write(src, f"rejected/{name}")

    buf.seek(0)
    filename = f"youdo_photo_{session_id}.zip"

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/{session_id}/json")
async def api_export_json(session_id: str):
    """Экспортирует результаты в JSON."""
    import json
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Сессия не найдена")

    if session.status != "analyzed":
        raise HTTPException(400, "Анализ ещё не выполнен")

    content = json.dumps({
        "session_id": session.id,
        "total": len(session.results),
        "accepted": len([r for r in session.results if r.get("accepted")]),
        "results": session.results,
    }, ensure_ascii=False, indent=2)

    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=results_{session_id}.json"},
    )
