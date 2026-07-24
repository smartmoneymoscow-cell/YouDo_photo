"""API: экспорт результатов с реальной конвертацией формата."""

import os
import io
import zipfile
import tempfile
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


def _convert_image(src_path: str, target_format: str, quality: int) -> bytes | None:
    """Конвертирует изображение в нужный формат. Возвращает bytes или None при ошибке."""
    try:
        from PIL import Image

        img = Image.open(src_path)

        fmt = target_format.lower().strip()
        if fmt in ("jpg", "jpeg"):
            img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
        elif fmt == "png":
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
        elif fmt == "webp":
            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=quality)
        else:
            # Неизвестный формат — возвращаем оригинал
            with open(src_path, "rb") as f:
                return f.read()

        return buf.getvalue()
    except Exception as e:
        print(f"[Export] Convert error {src_path}: {e}")
        return None


@router.post("/export/{session_id}/zip")
async def api_export_zip(session_id: str, req: ExportRequest):
    """
    Экспортирует фотографии в ZIP-архив с конвертацией формата.
    Использует стриминг, чтобы не забивать память.
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

    target_ext = req.format.lower().strip()
    if target_ext == "jpg":
        target_ext = "jpeg"  # Pillow needs "JPEG" not "JPG"

    # Собираем ZIP во временный файл (не в память!)
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Метаданные
            meta = f"YouDo Photo Export\nФормат: {req.format}\nКачество: {req.quality}\n"
            meta += f"Принято: {len(accepted)} из {len(session.results)}\n\n"
            meta += "Принятые кадры:\n"
            for r in accepted:
                meta += f"  #{r['rank']} {r['score']:.2%} {Path(r['path']).name}\n"
            zf.writestr("README.txt", meta)

            # Файлы с конвертацией
            for r in files_to_export:
                src = r["path"]
                if not os.path.exists(src):
                    continue

                folder = "accepted" if r.get("accepted") else "rejected"
                stem = Path(src).stem
                out_name = f"{stem}.{target_ext if target_ext != 'jpeg' else 'jpg'}"

                # Конвертируем
                converted = _convert_image(src, req.format, req.quality)
                if converted is not None:
                    zf.writestr(f"{folder}/{out_name}", converted)
                else:
                    # Конвертация не удалась — копируем оригинал
                    zf.write(src, f"{folder}/{Path(src).name}")

        # Стримим файл из диска
        def iter_file():
            with open(tmp_path, "rb") as f:
                while chunk := f.read(65536):
                    yield chunk
            os.unlink(tmp_path)

        filename = f"youdo_photo_{session_id}.zip"
        return StreamingResponse(
            iter_file(),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception:
        # Убираем временный файл при ошибке
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


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
