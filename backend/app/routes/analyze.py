"""API: AI-анализ фотографий."""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.app.services.session import get_session
from backend.app.services.analyzer import analyze_session

router = APIRouter(tags=["analyze"])


class AnalyzeRequest(BaseModel):
    model: str | None = Field(default=None, description="Модель эмбеддингов (auto-select по RAM)")
    threshold: float = Field(default=0.75, ge=0.0, le=1.0, description="Порог сходства")
    top_k: int | None = Field(default=None, description="Только top-K лучших")
    ref_method: str = Field(default="max", description="Метод сравнения: max/mean/weighted")
    max_side: int = Field(default=512, description="Макс. сторона при чтении")


@router.post("/analyze/{session_id}")
async def api_analyze(session_id: str, req: AnalyzeRequest):
    """
    Запускает AI-анализ: извлекает эмбеддинги и сравнивает с эталоном.

    Возвращает ранжированный список всех фото с оценками сходства.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Сессия не найдена")

    if not session.ref_files:
        raise HTTPException(400, "Нет эталонных файлов. Загрузите их на шаге 1.")

    if not session.photo_files:
        raise HTTPException(400, "Нет фотографий для анализа. Загрузите их на шаге 1.")

    result = analyze_session(
        session_id=session_id,
        ref_dir=session.ref_dir,
        photo_dir=session.photo_dir,
        model_name=req.model,
        threshold=req.threshold,
        top_k=req.top_k,
        ref_method=req.ref_method,
        max_side=req.max_side,
    )

    if result.get("status") == "error":
        raise HTTPException(400, result["error"])

    session.results = result.get("results", [])
    session.status = "analyzed"

    return result


@router.get("/analyze/{session_id}/results")
async def api_get_results(session_id: str):
    """Возвращает результаты анализа (без пересчёта)."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Сессия не найдена")

    if session.status != "analyzed":
        raise HTTPException(400, "Анализ ещё не выполнен")

    return {
        "session_id": session.id,
        "status": session.status,
        "total": len(session.results),
        "results": session.results,
    }


@router.get("/models")
async def api_list_models():
    """Возвращает доступные модели."""
    from core.embedding import MODEL_REGISTRY
    return MODEL_REGISTRY
