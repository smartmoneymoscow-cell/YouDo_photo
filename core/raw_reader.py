"""
Этап 1: Конвертация CR3/RAW → JPG/TIFF.

Поддерживает три движка:
- rawpy (LibRaw) — быстрый, встроенный
- RawTherapee CLI — лучшее качество демозаики, цвет, шумоподавление
- dcraw_emu (dcraw) — классический, минимальный
"""

import os
import subprocess
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import cv2
import numpy as np

RAW_EXTENSIONS = {
    '.cr3', '.cr2', '.nef', '.arw', '.raf', '.rw2', '.dng',
    '.raw', '.orf', '.srw', '.pef', '.3fr', '.kdc', '.mrw',
}

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp'}

# RawTherapee profiles для разных сценариев
PP3_PROFILES = {
    "default": None,  # Встроенные настройки RT
    "interior": """[Version]
AppVersion=5.11
Version=348

[White Balance]
Temperature=5500
Green=1.0
Equal=1.0
TemperatureBias=0

[Exposure]
Compensation=0
Brightness=0
Contrast=0
Saturation=5
HighlightCompr=30
ShadowCompr=30
Black=0
Highlight=0
Shadow=0

[Sharpening]
Enabled=true
Amount=40
Radius=0.5
Threshold=20
""",
    "high_quality": """[Version]
AppVersion=5.11
Version=348

[RAW]
Method=ahd

[Color Management]
InputProfile=(camera)

[Exposure]
Compensation=0
HighlightCompr=50
ShadowCompr=50

[Sharpening]
Enabled=true
Amount=30
Radius=0.7
""",
}


def _find_binary(name: str) -> str:
    """Ищет исполняемый файл в PATH."""
    result = subprocess.run(["which", name], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def _check_rawtherapee() -> str:
    """Находит rawtherapee-cli."""
    for name in ["rawtherapee-cli", "rawtherapee-cli.exe"]:
        path = _find_binary(name)
        if path:
            return path
    return ""


def _check_dcraw() -> str:
    """Находит dcraw_emu или dcraw."""
    for name in ["dcraw_emu", "dcraw"]:
        path = _find_binary(name)
        if path:
            return path
    return ""


class RawConverter:
    """Конвертер RAW файлов с поддержкой нескольких движков."""

    def __init__(self, engine: str = "auto", profile: str = "default"):
        """
        Args:
            engine: 'rawtherapee', 'dcraw', 'rawpy', или 'auto' (лучший доступный)
            profile: имя профиля PP3 для RawTherapee ('default', 'interior', 'high_quality')
        """
        self.profile_name = profile
        self._pp3_path = None

        if engine == "auto":
            if _check_rawtherapee():
                self.engine = "rawtherapee"
            elif _check_dcraw():
                self.engine = "dcraw"
            else:
                self.engine = "rawpy"
        else:
            self.engine = engine

        if self.engine == "rawtherapee":
            self._rt_path = _check_rawtherapee()
            if not self._rt_path:
                print("⚠️  RawTherapee не найден, переключаюсь на rawpy")
                self.engine = "rawpy"
            else:
                self._prepare_pp3()

        print(f"  Движок конвертации: {self.engine}")

    def _prepare_pp3(self):
        """Создаёт временный PP3-профиль."""
        if self.profile_name == "default":
            return
        profile_text = PP3_PROFILES.get(self.profile_name)
        if profile_text:
            fd, self._pp3_path = tempfile.mkstemp(suffix=".pp3")
            with os.fdopen(fd, 'w') as f:
                f.write(profile_text)

    def convert_one(self, raw_path: str, output_path: str = None,
                    quality: int = 95, max_side: int = 0) -> str:
        """
        Конвертирует один RAW файл.

        Args:
            raw_path: путь к RAW файлу
            output_path: путь для результата (auto если None)
            quality: качество JPG (1-100)
            max_side: максимальная сторона (0 = оригинал)

        Returns:
            путь к сконвертированному файлу
        """
        if output_path is None:
            output_path = str(Path(raw_path).with_suffix('.jpg'))

        if self.engine == "rawtherapee":
            return self._convert_rawtherapee(raw_path, output_path, quality, max_side)
        elif self.engine == "dcraw":
            return self._convert_dcraw(raw_path, output_path, quality)
        else:
            return self._convert_rawpy(raw_path, output_path, quality, max_side)

    def _convert_rawtherapee(self, raw_path: str, output_path: str,
                              quality: int, max_side: int) -> str:
        """RawTherapee CLI — лучшее качество."""
        cmd = [self._rt_path, "-o", output_path, "-b", str(quality), "-c", raw_path]

        if self._pp3_path:
            cmd.extend(["-p", self._pp3_path])

        # Высокое качество демозаики
        cmd.extend(["-js3", "3"])  # JPEG subsampling 4:4:4

        if max_side > 0:
            cmd.extend(["-r", "-s", f"{max_side}"])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"RawTherapee ошибка: {result.stderr[:500]}")

        return output_path

    def _convert_dcraw(self, raw_path: str, output_path: str, quality: int) -> str:
        """dcraw_emu — классический конвертер."""
        tiff_path = str(Path(output_path).with_suffix('.tiff'))
        cmd = [
            _check_dcraw(),
            "-6", "-W", "-o", "1",  # 16-bit, sRGB, auto WB
            "-T",  # TIFF output
            raw_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"dcraw ошибка: {result.stderr[:500]}")

        # TIFF → JPG
        img = cv2.imread(tiff_path)
        if img is None:
            raise RuntimeError(f"Не удалось прочитать TIFF: {tiff_path}")
        cv2.imwrite(output_path, img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        os.remove(tiff_path)

        return output_path

    def _convert_rawpy(self, raw_path: str, output_path: str,
                        quality: int, max_side: int) -> str:
        """rawpy (LibRaw) — быстрый встроенный конвертер."""
        import rawpy

        with rawpy.imread(raw_path) as raw:
            rgb = raw.postprocess(
                demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,
                use_camera_wb=True,
                output_color=rawpy.ColorSpace.sRGB,
                output_bps=8,
                no_auto_bright=False,
                bright=1.0,
            )

        if max_side > 0:
            h, w = rgb.shape[:2]
            if max(h, w) > max_side:
                scale = max_side / max(h, w)
                rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)),
                                 interpolation=cv2.INTER_AREA)

        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return output_path

    def batch_convert(self, raw_paths: list[str], output_dir: str = None,
                       quality: int = 95, max_side: int = 0,
                       workers: int = 4, progress_cb=None) -> list[str]:
        """
        Пакетная конвертация RAW → JPG.

        Args:
            raw_paths: список путей к RAW файлам
            output_dir: директория для результатов (auto = рядом с RAW)
            quality: качество JPG
            max_side: максимальная сторона
            workers: количество потоков
            progress_cb: callback(текущий, всего, имя_файла)

        Returns:
            список путей к сконвертированным файлам
        """
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        results = []
        total = len(raw_paths)
        done = 0

        def convert_single(raw_path):
            nonlocal done
            if output_dir:
                out = os.path.join(output_dir, Path(raw_path).stem + ".jpg")
            else:
                out = None
            try:
                result = self.convert_one(raw_path, out, quality, max_side)
                done += 1
                if progress_cb:
                    progress_cb(done, total, Path(raw_path).name)
                return result
            except Exception as e:
                done += 1
                if progress_cb:
                    progress_cb(done, total, Path(raw_path).name)
                print(f"  ✗ {Path(raw_path).name}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(convert_single, p): p for p in raw_paths}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)

        return sorted(results)

    def __del__(self):
        """Очистка временных файлов."""
        if self._pp3_path and os.path.exists(self._pp3_path):
            os.remove(self._pp3_path)


def read_image(path: str, max_side: int = 1024) -> np.ndarray:
    """Читает JPG/PNG/TIFF → numpy RGB."""
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Не удалось прочитать: {path}")
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]
    if max(h, w) > max_side:
        scale = max_side / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)),
                         interpolation=cv2.INTER_AREA)
    return img


def read_raw(path: str, max_side: int = 1024) -> np.ndarray:
    """Читает RAW через rawpy → numpy RGB."""
    import rawpy
    with rawpy.imread(path) as raw:
        rgb = raw.postprocess(
            demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,
            use_camera_wb=True,
            output_color=rawpy.ColorSpace.sRGB,
            output_bps=8,
            no_auto_bright=True,
        )
    h, w = rgb.shape[:2]
    if max(h, w) > max_side:
        scale = max_side / max(h, w)
        rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)),
                         interpolation=cv2.INTER_AREA)
    return rgb


def is_raw(path: str) -> bool:
    return Path(path).suffix.lower() in RAW_EXTENSIONS


def is_image(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def read_any(path: str, max_side: int = 1024) -> np.ndarray:
    """Читает любой поддерживаемый формат."""
    if is_raw(path):
        return read_raw(path, max_side)
    elif is_image(path):
        return read_image(path, max_side)
    else:
        raise ValueError(f"Неподдерживаемый формат: {path}")
