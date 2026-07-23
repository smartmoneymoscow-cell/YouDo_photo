"""Сервис: AI-анализ фотографий по эмбеддингам.

Memory-optimized: lazy imports, one-image-at-a-time processing.
"""

import os
import sys
import gc
import time
from pathlib import Path
from dataclasses import asdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))


_model_cache = {}
MODEL_FALLBACK = ["clip_vit_b32", "resnet50"]


def get_available_ram_mb():
    try:
        import psutil
        return psutil.virtual_memory().available / (1024 * 1024)
    except Exception:
        return 512


def pick_model(requested=None):
    available = get_available_ram_mb()
    if requested and requested in _model_cache:
        return requested
    if available >= 2000:
        return requested or "clip_vit_b32"
    if available >= 800:
        return requested if requested in ("clip_vit_b32", "resnet50") else "clip_vit_b32"
    return "resnet50"


def get_extractor(model_name=None, device=None):
    from core.embedding import EmbeddingExtractor

    model_name = pick_model(model_name or "clip_vit_b32")

    if model_name not in _model_cache:
        try:
            _model_cache[model_name] = EmbeddingExtractor(model_name=model_name, device=device)
        except (RuntimeError, MemoryError) as e:
            print(f"⚠️  OOM при загрузке {model_name}: {e}")
            gc.collect()
            for fallback in MODEL_FALLBACK:
                if fallback == model_name:
                    continue
                try:
                    _model_cache[fallback] = EmbeddingExtractor(model_name=fallback, device="cpu")
                    model_name = fallback
                    break
                except Exception:
                    continue
            else:
                raise RuntimeError(f"Не удалось загрузить модель. RAM: {get_available_ram_mb():.0f} MB.")
    return _model_cache[model_name]


def find_photos(directory):
    from core.raw_reader import RAW_EXTENSIONS, IMAGE_EXTENSIONS
    all_ext = RAW_EXTENSIONS | IMAGE_EXTENSIONS
    files = []
    for root, _, names in os.walk(directory):
        for f in sorted(names):
            if Path(f).suffix.lower() in all_ext:
                files.append(os.path.join(root, f))
    return files


def extract_embeddings_one_by_one(paths, extractor, max_side=1024):
    """Extract embeddings one image at a time to minimize RAM usage."""
    from core.raw_reader import read_any
    import numpy as np

    embeddings = []
    valid_paths = []

    for i, p in enumerate(paths):
        try:
            img = read_any(p, max_side=max_side)
            emb = extractor.extract(img)
            embeddings.append(emb)
            valid_paths.append(p)
            # Free image memory immediately
            del img
            if (i + 1) % 5 == 0:
                gc.collect()
        except Exception as e:
            print(f"  ✗ {Path(p).name}: {e}")

    if not embeddings:
        return np.array([]), []
    return np.stack(embeddings).astype(np.float32), valid_paths


def analyze_session(
    session_id,
    ref_dir,
    photo_dir,
    model_name=None,
    threshold=0.75,
    top_k=None,
    ref_method="max",
    max_side=512,
):
    """Полный анализ: загрузка → эмбеддинги → сравнение → отбор."""
    from core.similarity import select_best, select_with_multi_reference

    t0 = time.time()

    ref_paths = find_photos(ref_dir)
    photo_paths = find_photos(photo_dir)

    ref_set = set(os.path.abspath(p) for p in ref_paths)
    photo_paths = [p for p in photo_paths if os.path.abspath(p) not in ref_set]

    if not ref_paths:
        return {"error": "Нет эталонных изображений", "status": "error"}
    if not photo_paths:
        return {"error": "Нет фотографий для анализа", "status": "error"}

    extractor = get_extractor(model_name)

    # Process one image at a time (memory-efficient)
    ref_embeddings, valid_ref = extract_embeddings_one_by_one(ref_paths, extractor, max_side)
    gc.collect()

    photo_embeddings, valid_photos = extract_embeddings_one_by_one(photo_paths, extractor, max_side)
    gc.collect()

    if len(valid_ref) == 0:
        return {"error": "Не удалось загрузить эталоны", "status": "error"}
    if len(valid_photos) == 0:
        return {"error": "Не удалось загрузить фотографии", "status": "error"}

    # Comparison (numpy only, lightweight)
    if len(ref_embeddings) > 1:
        results = select_with_multi_reference(
            valid_photos, photo_embeddings, ref_embeddings,
            threshold=threshold, method=ref_method,
        )
    else:
        results = select_best(
            valid_photos, photo_embeddings, ref_embeddings[0],
            threshold=threshold, top_k=top_k,
        )

    del ref_embeddings, photo_embeddings
    gc.collect()

    accepted = [r for r in results if r.accepted]
    rejected = [r for r in results if not r.accepted]
    elapsed = time.time() - t0

    return {
        "status": "ok",
        "session_id": session_id,
        "elapsed_sec": round(elapsed, 1),
        "model": extractor.model_name,
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
