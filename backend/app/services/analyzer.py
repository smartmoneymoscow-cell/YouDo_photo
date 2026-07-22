"""Сервис: AI-анализ фотографий по эмбеддингам."""

import os
import sys
import time
from pathlib import Path
from dataclasses import asdict

# Добавляем корень проекта в путь для импорта core
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import numpy as np
from core.raw_reader import read_any, is_raw, RAW_EXTENSIONS, IMAGE_EXTENSIONS
from core.embedding import EmbeddingExtractor, MODEL_REGISTRY
from core.similarity import (
    cosine_similarity_batch, select_best, select_with_multi_reference,
    MatchResult, FAISSIndex, apply_threshold,
)


# Глобальный кэш моделей (чтобы не загружать каждый раз)
_model_cache: dict[str, EmbeddingExtractor] = {}


def get_extractor(model_name: str = "openclip_vit_l14", device: str = None) -> EmbeddingExtractor:
    """Получает или создаёт экстрактор эмбеддингов (с кэшированием)."""
    if model_name not in _model_cache:
        _model_cache[model_name] = EmbeddingExtractor(model_name=model_name, device=device)
    return _model_cache[model_name]


def load_images(paths: list[str], max_side: int = 1024) -> tuple[list, list]:
    """Загружает изображения, возвращает (массивы, валидные_пути)."""
    images = []
    valid = []
    for p in paths:
        try:
            img = read_any(p, max_side=max_side)
            images.append(img)
            valid.append(p)
        except Exception as e:
            print(f"  ✗ {Path(p).name}: {e}")
    return images, valid


def find_photos(directory: str) -> list[str]:
    """Находит все RAW и изображения в директории."""
    all_ext = RAW_EXTENSIONS | IMAGE_EXTENSIONS
    files = []
    for root, _, names in os.walk(directory):
        for f in sorted(names):
            if Path(f).suffix.lower() in all_ext:
                files.append(os.path.join(root, f))
    return files


def analyze_session(
    session_id: str,
    ref_dir: str,
    photo_dir: str,
    model_name: str = "openclip_vit_l14",
    threshold: float = 0.75,
    top_k: int = None,
    ref_method: str = "max",
    max_side: int = 1024,
) -> dict:
    """
    Полный анализ: загрузка → эмбеддинги → сравнение → отбор.

    Returns:
        dict с результатами и статистикой
    """
    t0 = time.time()

    # 1. Найти файлы
    ref_paths = find_photos(ref_dir)
    photo_paths = find_photos(photo_dir)

    # Исключаем эталоны из фото
    ref_set = set(os.path.abspath(p) for p in ref_paths)
    photo_paths = [p for p in photo_paths if os.path.abspath(p) not in ref_set]

    if not ref_paths:
        return {"error": "Нет эталонных изображений", "status": "error"}
    if not photo_paths:
        return {"error": "Нет фотографий для анализа", "status": "error"}

    # 2. Загрузить и извлечь эмбеддинги
    extractor = get_extractor(model_name)

    ref_images, valid_ref = load_images(ref_paths, max_side)
    photo_images, valid_photos = load_images(photo_paths, max_side)

    if not ref_images:
        return {"error": "Не удалось загрузить эталоны", "status": "error"}
    if not photo_images:
        return {"error": "Не удалось загрузить фотографии", "status": "error"}

    ref_embeddings = extractor.extract_batch(ref_images)
    photo_embeddings = extractor.extract_batch(photo_images)

    # 3. Сравнение
    if len(ref_embeddings) > 1:
        results = select_with_multi_reference(
            valid_photos, photo_embeddings, ref_embeddings,
            threshold=threshold, method=ref_method,
        )
    else:
        ref_mean = ref_embeddings[0]
        results = select_best(
            valid_photos, photo_embeddings, ref_mean,
            threshold=threshold, top_k=top_k,
        )

    # 4. Формируем ответ
    accepted = [r for r in results if r.accepted]
    rejected = [r for r in results if not r.accepted]
    elapsed = time.time() - t0

    return {
        "status": "ok",
        "session_id": session_id,
        "elapsed_sec": round(elapsed, 1),
        "model": model_name,
        "model_dim": extractor.dim,
        "threshold": threshold,
        "total": len(results),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "best_score": round(results[0].score, 4) if results else 0,
        "worst_score": round(results[-1].score, 4) if results else 0,
        "results": [asdict(r) for r in results],
        "accepted": [asdict(r) for r in accepted],
        "rejected": [asdict(r) for r in rejected],
    }
