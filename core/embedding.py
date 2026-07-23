"""
Этап 2: Извлечение эмбеддингов из изображений.

Поддерживает 4 модели (от быстрой к точной):
- ResNet50 — 2048-d, ImageNet, быстро
- CLIP ViT-B/32 — 512-d, OpenAI, хорошо для семантики
- OpenCLIP ViT-L/14 — 768-d, LAION, отличное визуальное сходство
- DINOv2 ViT-S/14 — 384-d, Meta, лучшее для визуального сходства без текста
"""

import numpy as np
import torch
import torch.nn as nn
import torchvision.transforms as transforms
from PIL import Image


# ─── Стандартная предобработка для ImageNet/CLIP ───
IMAGENET_TRANSFORM = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])

CLIP_TRANSFORM = transforms.Compose([
    transforms.Resize(224, interpolation=transforms.InterpolationMode.BICUBIC),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.48145466, 0.4578275, 0.40821073],
                         std=[0.26862954, 0.26130258, 0.27577711]),
])


# ─── Реестр моделей ───
MODEL_REGISTRY = {
    "resnet50": {
        "dim": 2048,
        "transform": "imagenet",
        "description": "ResNet50 ImageNet — быстрый базовый",
    },
    "clip_vit_b32": {
        "dim": 512,
        "transform": "clip",
        "description": "CLIP ViT-B/32 — семантический",
    },
    "openclip_vit_l14": {
        "dim": 768,
        "transform": "clip",
        "description": "OpenCLIP ViT-L/14 LAION-2B — лучший баланс",
    },
    "dinov2_vits14": {
        "dim": 384,
        "transform": "imagenet",
        "description": "DINOv2 ViT-S/14 — визуальное сходство",
    },
}


class EmbeddingExtractor:
    """Извлекает векторные описания (эмбеддинги) из изображений."""

    def __init__(self, model_name: str = "clip_vit_b32", device: str = None):
        """
        Args:
            model_name: имя модели из MODEL_REGISTRY
            device: 'cuda' / 'cpu' / None (авто)
        """
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model_name = model_name
        self.model = None
        self.transform = None
        self.dim = MODEL_REGISTRY[model_name]["dim"]

        print(f"  Загрузка модели: {model_name} ({self.dim}-d) на {self.device}")
        self._setup(model_name)

    def _setup(self, model_name: str):
        if model_name == "resnet50":
            self._setup_resnet50()
        elif model_name == "clip_vit_b32":
            self._setup_clip_vit_b32()
        elif model_name == "openclip_vit_l14":
            self._setup_openclip_vit_l14()
        elif model_name == "dinov2_vits14":
            self._setup_dinov2()
        else:
            raise ValueError(
                f"Неизвестная модель: {model_name}. "
                f"Доступные: {list(MODEL_REGISTRY.keys())}"
            )

    def _setup_resnet50(self):
        from torchvision.models import resnet50, ResNet50_Weights
        weights = ResNet50_Weights.IMAGENET1K_V2
        model = resnet50(weights=weights)
        self.model = nn.Sequential(*list(model.children())[:-1])
        self.model.eval().to(self.device)
        self.transform = IMAGENET_TRANSFORM

    def _setup_clip_vit_b32(self):
        try:
            import open_clip
        except ImportError:
            raise ImportError("pip install open-clip-torch")
        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s347b_k799e"
        )
        self.model = model.visual
        self.model.eval().to(self.device)
        self.transform = preprocess

    def _setup_openclip_vit_l14(self):
        try:
            import open_clip
        except ImportError:
            raise ImportError(
                "Для OpenCLIP: pip install open-clip-torch\n"
                "Это лучшая модель для визуального сходства."
            )
        model, _, _ = open_clip.create_model_and_transforms(
            "ViT-L-14", pretrained="laion2b_s32b_b82k"
        )
        self.model = model.visual
        self.model.eval().to(self.device)
        # OpenCLIP использует свою предобработку
        _, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-L-14", pretrained="laion2b_s32b_b82k"
        )
        self.transform = preprocess

    def _setup_dinov2(self):
        self.model = torch.hub.load('facebookresearch/dinov2', 'dinov2_vits14')
        self.model.eval().to(self.device)
        self.transform = IMAGENET_TRANSFORM

    def extract(self, image: np.ndarray) -> np.ndarray:
        """
        Извлекает эмбеддинг из одного изображения.

        Args:
            image: numpy array (H, W, 3) dtype=uint8, RGB

        Returns:
            numpy array (dim,) dtype=float32, L2-нормализованный
        """
        pil_img = Image.fromarray(image)
        tensor = self.transform(pil_img).unsqueeze(0).to(self.device)

        with torch.no_grad():
            features = self.model(tensor)

        # Flatten (ResNet50 даёт [1, 2048, 1, 1], CLIP даёт [1, dim])
        if features.dim() > 2:
            features = features.flatten(1)

        # L2-нормализация
        features = torch.nn.functional.normalize(features, p=2, dim=1)
        return features.cpu().numpy().flatten().astype(np.float32)

    def extract_batch(self, images: list[np.ndarray], batch_size: int = 8) -> np.ndarray:
        """
        Пакетное извлечение эмбеддингов.

        Args:
            images: список numpy массивов (H, W, 3) uint8
            batch_size: размер батча

        Returns:
            numpy array (N, dim) dtype=float32
        """
        all_embeddings = []

        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            tensors = torch.stack([
                self.transform(Image.fromarray(img)) for img in batch
            ]).to(self.device)

            with torch.no_grad():
                features = self.model(tensors)

            if features.dim() > 2:
                features = features.flatten(1)

            features = torch.nn.functional.normalize(features, p=2, dim=1)
            all_embeddings.append(features.cpu().numpy())

        return np.vstack(all_embeddings).astype(np.float32)

    @staticmethod
    def list_models() -> dict:
        """Возвращает доступные модели."""
        return MODEL_REGISTRY
