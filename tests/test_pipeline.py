"""Тест пайплайна на синтетических данных (без реальных CR3 файлов)."""

import sys, os, importlib.util

# Прямая загрузка similarity.py, чтобы не тянуть rawpy/torch через __init__.py
_spec = importlib.util.spec_from_file_location(
    "similarity",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "core", "similarity.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

cosine_similarity = _mod.cosine_similarity
cosine_similarity_batch = _mod.cosine_similarity_batch
select_best = _mod.select_best

import numpy as np


def test_cosine_similarity():
    """Проверка косинусного сходства."""
    a = np.array([1.0, 0.0, 0.0])
    b = np.array([1.0, 0.0, 0.0])
    assert abs(cosine_similarity(a, b) - 1.0) < 1e-6

    c = np.array([0.0, 1.0, 0.0])
    assert abs(cosine_similarity(a, c)) < 1e-6

    d = np.array([-1.0, 0.0, 0.0])
    assert abs(cosine_similarity(a, d) - (-1.0)) < 1e-6

    print("✓ cosine_similarity OK")


def test_batch_similarity():
    """Проверка батчевого сходства."""
    embeddings = np.array([
        [1.0, 0.0, 0.0],
        [0.7, 0.7, 0.0],
        [0.0, 1.0, 0.0],
    ], dtype=np.float32)

    ref = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    scores = cosine_similarity_batch(embeddings, ref)

    assert scores.shape == (3,)
    assert scores[0] > scores[1] > scores[2]
    print(f"✓ batch_similarity OK (scores: {scores})")


def test_select_best():
    """Проверка отбора лучших кадров."""
    paths = ["photo_cr3_001.cr3", "photo_cr3_002.cr3", "photo_cr3_003.cr3", "photo_cr3_004.cr3"]

    embeddings = np.array([
        [0.95, 0.30, 0.00],
        [0.80, 0.60, 0.00],
        [0.20, 0.98, 0.00],
        [0.90, 0.44, 0.00],
    ], dtype=np.float32)

    ref = np.array([1.0, 0.0, 0.0], dtype=np.float32)

    results = select_best(paths, embeddings, ref, threshold=0.8)

    accepted = [r for r in results if r.accepted]
    print(f"✓ select_best OK: {len(accepted)} принято из {len(results)}")
    for r in results:
        print(f"    #{r.rank} {r.score:.2%} {'✅' if r.accepted else '❌'} {r.path}")

    assert results[0].rank == 1
    assert results[0].score >= results[-1].score


if __name__ == "__main__":
    test_cosine_similarity()
    test_batch_similarity()
    test_select_best()
    print("\n✅ Все тесты пройдены")
