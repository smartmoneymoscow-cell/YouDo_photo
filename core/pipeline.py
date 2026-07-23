"""
Основной пайплайн: конвертация → эмбеддинги → поиск → отбор.

Этапы:
1. RawTherapee/dcraw/rawpy: CR3 → JPG (лучшая цветопередача)
2. OpenCLIP/CLIP/DINOv2/ResNet50: JPG → эмбеддинг (векторный "отпечаток")
3. Косинусное сходство / FAISS: сравнение с эталоном
4. Отбор по порогу
"""

import os
import time
import json
from pathlib import Path
from dataclasses import asdict

import numpy as np

from .raw_reader import (
    RawConverter, read_any, read_image, is_raw, is_image,
    RAW_EXTENSIONS, IMAGE_EXTENSIONS,
)
from .embedding import EmbeddingExtractor, MODEL_REGISTRY
from .similarity import (
    select_best, select_with_multi_reference, MatchResult,
    FAISSIndex, apply_threshold,
)


class PhotoSelector:
    """
    Полный пайплайн: CR3/RAW → эмбеддинги → сравнение с эталоном → отбор.
    """

    def __init__(
        self,
        model_name: str = "clip_vit_b32",
        device: str = None,
        max_side: int = 1024,
        raw_engine: str = "auto",
        raw_profile: str = "interior",
    ):
        """
        Args:
            model_name: модель для эмбеддингов (см. MODEL_REGISTRY)
            device: 'cuda' / 'cpu' / None (авто)
            max_side: максимальная сторона при чтении
            raw_engine: движок RAW конвертации ('auto', 'rawtherapee', 'dcraw', 'rawpy')
            raw_profile: профиль RawTherapee ('default', 'interior', 'high_quality')
        """
        self.max_side = max_side

        # Конвертер RAW
        self.converter = RawConverter(engine=raw_engine, profile=raw_profile)

        # Экстрактор эмбеддингов
        self.extractor = EmbeddingExtractor(model_name=model_name, device=device)

        # FAISS индекс (ленивая инициализация)
        self._faiss = None

    def _find_files(self, directory: str, extensions: set) -> list[str]:
        """Находит файлы нужных расширений в директории (рекурсивно)."""
        files = []
        for root, _, filenames in os.walk(directory):
            for f in sorted(filenames):
                if Path(f).suffix.lower() in extensions:
                    files.append(os.path.join(root, f))
        return files

    def _load_and_extract(self, paths: list[str], label: str = "") -> tuple:
        """Загружает изображения и извлекает эмбеддинги."""
        images = []
        valid_paths = []

        for i, path in enumerate(paths):
            try:
                img = read_any(path, max_side=self.max_side)
                images.append(img)
                valid_paths.append(path)
                print(f"  [{label}] {i+1}/{len(paths)}: {Path(path).name} ✓")
            except Exception as e:
                print(f"  [{label}] {i+1}/{len(paths)}: {Path(path).name} ✗ ({e})")

        if not images:
            raise ValueError(f"Не удалось загрузить ни одного файла из {label}")

        print(f"  Извлечение эмбеддингов ({len(images)} файлов, модель: {self.extractor.model_name})...")
        embeddings = self.extractor.extract_batch(images)
        return embeddings, valid_paths

    def run(
        self,
        reference_paths: list[str],
        photo_paths: list[str] = None,
        photo_dir: str = None,
        threshold: float = 0.75,
        top_k: int = None,
        ref_method: str = "max",
        use_faiss: bool = False,
        output_json: str = None,
    ) -> list[MatchResult]:
        """
        Запускает полный пайплайн отбора.

        Args:
            reference_paths: пути к эталонным JPG (1 или несколько)
            photo_paths: явный список путей к CR3/RAW фото
            photo_dir: директория с фото (альтернатива photo_paths)
            threshold: порог сходства [0..1]
            top_k: вернуть только top-K
            ref_method: 'max', 'mean', 'weighted' при нескольких эталонах
            use_faiss: использовать FAISS для поиска (для больших баз)
            output_json: путь для сохранения результатов

        Returns:
            список MatchResult, отсортированный по убыванию score
        """
        t0 = time.time()

        # ── 1. Эталоны ──
        print(f"\n{'='*60}")
        print(f"📐 ШАГ 1: Загрузка эталонов ({len(reference_paths)} шт.)")
        print(f"{'='*60}")
        ref_embeddings, valid_ref_paths = self._load_and_extract(reference_paths, "эталон")

        # Средний эмбеддинг эталонов
        if len(ref_embeddings) > 1:
            ref_mean = ref_embeddings.mean(axis=0)
            ref_mean = ref_mean / (np.linalg.norm(ref_mean) + 1e-8)
            print(f"  Усреднённый эталон из {len(ref_embeddings)} reference-фото")
        else:
            ref_mean = ref_embeddings[0]

        # ── 2. Фотографии ──
        if photo_paths is None:
            if photo_dir is None:
                raise ValueError("Укажите photo_paths или photo_dir")
            all_ext = RAW_EXTENSIONS | IMAGE_EXTENSIONS
            photo_paths = self._find_files(photo_dir, all_ext)
            # Исключаем эталоны
            ref_set = set(os.path.abspath(p) for p in reference_paths)
            photo_paths = [p for p in photo_paths if os.path.abspath(p) not in ref_set]

        if not photo_paths:
            raise ValueError("Нет фотографий для анализа")

        print(f"\n{'='*60}")
        print(f"📸 ШАГ 2: Загрузка фотографий ({len(photo_paths)} шт.)")
        print(f"{'='*60}")
        photo_embeddings, valid_photo_paths = self._load_and_extract(photo_paths, "фото")

        # ── 3. Сравнение ──
        print(f"\n{'='*60}")
        print(f"🔍 ШАГ 3: Сравнение с эталоном (порог: {threshold:.0%})")
        print(f"{'='*60}")

        if use_faiss and len(valid_photo_paths) > 100:
            print(f"  Используем FAISS для поиска в базе {len(valid_photo_paths)} фото")
            self._faiss = FAISSIndex(dimension=self.extractor.dim)
            self._faiss.build(photo_embeddings, valid_photo_paths)
            faiss_results = self._faiss.search(ref_mean, top_k=top_k or len(valid_photo_paths))
            results = apply_threshold(faiss_results, threshold)
        elif len(ref_embeddings) > 1:
            results = select_with_multi_reference(
                valid_photo_paths, photo_embeddings, ref_embeddings,
                threshold=threshold, method=ref_method,
            )
        else:
            results = select_best(
                valid_photo_paths, photo_embeddings, ref_mean,
                threshold=threshold, top_k=top_k,
            )

        # ── 4. Статистика ──
        accepted = [r for r in results if r.accepted]
        rejected = [r for r in results if not r.accepted]
        elapsed = time.time() - t0

        print(f"\n{'='*60}")
        print(f"✅ РЕЗУЛЬТАТЫ ({elapsed:.1f} сек)")
        print(f"{'='*60}")
        print(f"  Модель:             {self.extractor.model_name} ({self.extractor.dim}-d)")
        print(f"  Движок RAW:         {self.converter.engine}")
        print(f"  Всего проанализировано: {len(results)}")
        print(f"  Принято (≥ {threshold:.0%}):   {len(accepted)}")
        print(f"  Отклонено:              {len(rejected)}")
        if results:
            print(f"  Лучший скор:            {results[0].score:.2%}")
            print(f"  Худший скор:            {results[-1].score:.2%}")

        if accepted:
            print(f"\n  📋 Принятые кадры:")
            for r in accepted[:30]:  # Показать первые 30
                print(f"    #{r.rank:2d}  {r.score:.2%}  {Path(r.path).name}")
            if len(accepted) > 30:
                print(f"    ... и ещё {len(accepted) - 30}")

        # Сохранение
        if output_json:
            self.results_to_json(results, output_json)

        return results

    @staticmethod
    def results_to_json(results: list[MatchResult], output_path: str = None) -> str:
        """Экспорт результатов в JSON."""
        data = {
            "total": len(results),
            "accepted": len([r for r in results if r.accepted]),
            "results": [asdict(r) for r in results],
        }
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json_str)
            print(f"  💾 Сохранено: {output_path}")
        return json_str

    @staticmethod
    def list_models() -> dict:
        """Возвращает доступные модели."""
        return MODEL_REGISTRY
