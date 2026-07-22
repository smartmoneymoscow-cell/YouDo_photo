#!/usr/bin/env python3
"""
CLI для AI-отбора фотографий по сходству с эталоном.

Использование:
    python run.py --ref reference.jpg --photos ./photos/ --threshold 0.75
    python run.py --ref ref1.jpg ref2.jpg --photos ./cr3_folder/ --model openclip_vit_l14 --top-k 10
    python run.py --ref ref.jpg --photos-dir ./raw/ --model dinov2_vits14 --faiss --output results.json

Модели:
    resnet50           — 2048-d, ImageNet, быстро
    clip_vit_b32       — 512-d, OpenAI CLIP
    openclip_vit_l14   — 768-d, OpenCLIP LAION-2B (рекомендуется)
    dinov2_vits14      — 384-d, Meta DINOv2

Движки RAW:
    rawtherapee        — RawTherapee CLI (лучшее качество)
    dcraw              — dcraw_emu
    rawpy              — LibRaw (встроенный, по умолчанию)
    auto               — лучший доступный
"""

import argparse
import sys
from core.pipeline import PhotoSelector
from core.embedding import MODEL_REGISTRY


def main():
    parser = argparse.ArgumentParser(
        description="YouDo Photo — AI-отбор фотографий по сходству с эталоном",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Доступные модели:
{chr(10).join(f'  {k:25s} — {v["description"]} ({v["dim"]}-d)' for k, v in MODEL_REGISTRY.items())}

Примеры:
  python run.py --ref ref.jpg --photos-dir ./photos/
  python run.py --ref ref.jpg --photos-dir ./cr3/ --model openclip_vit_l14 --threshold 0.8
  python run.py --ref ref1.jpg ref2.jpg --photos-dir ./raw/ --top-k 20 --faiss
  python run.py --ref ref.jpg --photos-dir ./raw/ --raw-engine rawtherapee --raw-profile interior
        """,
    )

    parser.add_argument("--ref", nargs="+", required=True, help="Эталонный JPG (можно несколько)")
    parser.add_argument("--photos", nargs="+", default=None, help="Пути к CR3/RAW фото")
    parser.add_argument("--photos-dir", default=None, help="Директория с фото")
    parser.add_argument("--threshold", type=float, default=0.75, help="Порог сходства [0..1]")
    parser.add_argument("--top-k", type=int, default=None, help="Только top-K лучших")
    parser.add_argument("--model", choices=list(MODEL_REGISTRY.keys()), default="openclip_vit_l14",
                        help="Модель для эмбеддингов")
    parser.add_argument("--device", choices=["cuda", "cpu"], default=None, help="Устройство")
    parser.add_argument("--max-side", type=int, default=1024, help="Макс. сторона при чтении")
    parser.add_argument("--ref-method", choices=["max", "mean", "weighted"], default="max",
                        help="Метод сравнения с несколькими эталонами")
    parser.add_argument("--raw-engine", choices=["auto", "rawtherapee", "dcraw", "rawpy"],
                        default="auto", help="Движок RAW конвертации")
    parser.add_argument("--raw-profile", choices=["default", "interior", "high_quality"],
                        default="interior", help="Профиль RawTherapee")
    parser.add_argument("--faiss", action="store_true", help="Использовать FAISS для поиска")
    parser.add_argument("--output", "-o", default=None, help="Сохранить результаты в JSON")

    args = parser.parse_args()

    if not args.photos and not args.photos_dir:
        parser.error("Укажите --photos или --photos-dir")

    selector = PhotoSelector(
        model_name=args.model,
        device=args.device,
        max_side=args.max_side,
        raw_engine=args.raw_engine,
        raw_profile=args.raw_profile,
    )

    results = selector.run(
        reference_paths=args.ref,
        photo_paths=args.photos,
        photo_dir=args.photos_dir,
        threshold=args.threshold,
        top_k=args.top_k,
        ref_method=args.ref_method,
        use_faiss=args.faiss,
        output_json=args.output,
    )

    accepted = [r for r in results if r.accepted]
    print(f"\n{'='*60}")
    if accepted:
        print(f"✅ Готово. Принято {len(accepted)} из {len(results)} кадров.")
    else:
        print(f"⚠️  Ни один кадр не прошёл порог {args.threshold:.0%}.")
    print(f"{'='*60}")

    return 0 if accepted else 1


if __name__ == "__main__":
    sys.exit(main())
