"""
Этап 3+4: Сравнение эмбеддингов и поиск похожих изображений.

Поддерживает:
- Косинусное сходство (numpy) — для небольших коллекций
- FAISS индекс — для быстрого поиска в базе 100k+ изображений
- Множественные эталоны (max/mean/weighted)
"""

import numpy as np
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class MatchResult:
    """Результат сравнения одного фото с эталоном."""
    path: str
    score: float          # косинусное сходство [0..1]
    rank: int             # позиция в рейтинге (1 = лучший)
    accepted: bool        # выше порога?
    source: str = ""      # 'raw' / 'jpg' / 'ref'


# ═══════════════════════════════════════════════════════
#  Косинусное сходство (numpy)
# ═══════════════════════════════════════════════════════

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Косинусное сходство между двумя векторами."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def cosine_similarity_batch(embeddings: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """
    Косинусное сходство N векторов с одним эталоном.

    Args:
        embeddings: (N, D) — эмбеддинги всех фото
        reference: (D,) — эмбеддинг эталона

    Returns:
        (N,) — массив скоров [0..1]
    """
    ref_norm = reference / (np.linalg.norm(reference) + 1e-8)
    emb_norm = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)
    return np.dot(emb_norm, ref_norm).astype(np.float32)


# ═══════════════════════════════════════════════════════
#  FAISS — быстрый поиск в больших базах
# ═══════════════════════════════════════════════════════

class FAISSIndex:
    """
    FAISS-индекс для быстрого поиска похожих изображений.
    Работает с L2-нормализованными векторами → cosine similarity.
    """

    def __init__(self, dimension: int, use_gpu: bool = False):
        """
        Args:
            dimension: размерность эмбеддингов
            use_gpu: использовать GPU для FAISS (нужен faiss-gpu)
        """
        try:
            import faiss
        except ImportError:
            raise ImportError(
                "Для FAISS: pip install faiss-cpu  (или faiss-gpu для GPU)\n"
                "FAISS нужен для быстрого поиска в базе 100k+ изображений."
            )

        self.dimension = dimension
        self.faiss = faiss
        self.index = None
        self.paths = []
        self.use_gpu = use_gpu

    def build(self, embeddings: np.ndarray, paths: list[str]):
        """
        Строит индекс из эмбеддингов.

        Args:
            embeddings: (N, D) L2-нормализованные вектора
            paths: пути к файлам (в том же порядке)
        """
        import faiss

        n = embeddings.shape[0]

        # Выбор индекса в зависимости от размера базы
        if n < 1000:
            # Маленькая база — плоский индекс (точный поиск)
            self.index = faiss.IndexFlatIP(self.dimension)  # Inner Product = cosine для нормализованных
        elif n < 100_000:
            # Средняя база — IVF с квантизацией
            nlist = min(int(np.sqrt(n)), 256)
            quantizer = faiss.IndexFlatIP(self.dimension)
            self.index = faiss.IndexIVFFlat(quantizer, self.dimension, nlist,
                                            faiss.METRIC_INNER_PRODUCT)
            self.index.train(embeddings)
            self.index.nprobe = min(nlist // 4, 32)
        else:
            # Большая база — IVF + PQ (Product Quantization)
            nlist = min(int(np.sqrt(n)), 1024)
            m = 32  # количество subquantizers
            quantizer = faiss.IndexFlatIP(self.dimension)
            self.index = faiss.IndexIVFPQ(quantizer, self.dimension, nlist, m, 8,
                                          faiss.METRIC_INNER_PRODUCT)
            self.index.train(embeddings)
            self.index.nprobe = 64

        # Нормализация перед добавлением
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)
        self.paths = list(paths)

        print(f"  FAISS индекс: {n} векторов, тип: {type(self.index).__name__}")

    def search(self, query: np.ndarray, top_k: int = 50) -> list[MatchResult]:
        """
        Ищет top-K ближайших к query.

        Args:
            query: (D,) L2-нормализованный вектор
            top_k: количество результатов

        Returns:
            список MatchResult, отсортированный по убыванию score
        """
        import faiss

        q = query.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(q)

        scores, indices = self.index.search(q, min(top_k, len(self.paths)))

        results = []
        for rank, (idx, score) in enumerate(zip(indices[0], scores[0]), 1):
            if idx < 0:
                continue
            results.append(MatchResult(
                path=self.paths[idx],
                score=round(float(score), 4),
                rank=rank,
                accepted=score >= 0,  # Порог применяется отдельно
            ))

        return results

    def search_batch(self, queries: np.ndarray, top_k: int = 50) -> list[list[MatchResult]]:
        """Пакетный поиск для нескольких запросов."""
        import faiss

        q = queries.astype(np.float32)
        faiss.normalize_L2(q)

        scores, indices = self.index.search(q, min(top_k, len(self.paths)))

        all_results = []
        for q_scores, q_indices in zip(scores, indices):
            results = []
            for rank, (idx, score) in enumerate(zip(q_indices, q_scores), 1):
                if idx < 0:
                    continue
                results.append(MatchResult(
                    path=self.paths[idx],
                    score=round(float(score), 4),
                    rank=rank,
                    accepted=True,
                ))
            all_results.append(results)

        return all_results

    def save(self, path: str):
        """Сохраняет индекс на диск."""
        self.faiss.write_index(self.index, path)

    def load(self, path: str):
        """Загружает индекс с диска."""
        self.index = self.faiss.read_index(path)


# ═══════════════════════════════════════════════════════
#  Отбор лучших кадров
# ═══════════════════════════════════════════════════════

def select_best(
    paths: list[str],
    embeddings: np.ndarray,
    reference_embedding: np.ndarray,
    threshold: float = 0.75,
    top_k: int = None,
) -> list[MatchResult]:
    """
    Отбирает лучшие кадры по сходству с эталоном.
    """
    scores = cosine_similarity_batch(embeddings, reference_embedding)
    sorted_indices = np.argsort(-scores)

    results = []
    for rank, idx in enumerate(sorted_indices, 1):
        score = float(scores[idx])
        results.append(MatchResult(
            path=paths[idx],
            score=round(score, 4),
            rank=rank,
            accepted=score >= threshold,
        ))

    if top_k is not None:
        results = results[:top_k]

    return results


def select_with_multi_reference(
    paths: list[str],
    embeddings: np.ndarray,
    reference_embeddings: np.ndarray,
    threshold: float = 0.75,
    method: str = "max",
) -> list[MatchResult]:
    """
    Отбор с учётом нескольких эталонов.

    Args:
        method: 'max' — максимум сходства с любым эталоном
                'mean' — среднее сходство
                'weighted' — взвешенное (первый эталон весит больше)
    """
    all_scores = []
    for ref_emb in reference_embeddings:
        scores = cosine_similarity_batch(embeddings, ref_emb)
        all_scores.append(scores)

    scores_matrix = np.stack(all_scores)  # (M, N)

    if method == "max":
        final_scores = scores_matrix.max(axis=0)
    elif method == "mean":
        final_scores = scores_matrix.mean(axis=0)
    elif method == "weighted":
        # Первый эталон — основной (вес 0.6), остальные поровну
        weights = np.ones(len(reference_embeddings))
        weights[0] = 0.6
        weights[1:] = 0.4 / max(len(reference_embeddings) - 1, 1)
        final_scores = np.average(scores_matrix, axis=0, weights=weights)
    else:
        raise ValueError(f"Неизвестный method: {method}")

    sorted_indices = np.argsort(-final_scores)
    results = []
    for rank, idx in enumerate(sorted_indices, 1):
        score = float(final_scores[idx])
        results.append(MatchResult(
            path=paths[idx],
            score=round(score, 4),
            rank=rank,
            accepted=score >= threshold,
        ))

    return results


def apply_threshold(results: list[MatchResult], threshold: float) -> list[MatchResult]:
    """Применяет порог к уже посчитанным результатам."""
    for r in results:
        r.accepted = r.score >= threshold
    return results
