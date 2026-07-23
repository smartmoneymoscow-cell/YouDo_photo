"""Интеграционные тесты: загрузка файлов всех форматов + скачивание."""

import io
import os
import sys
import json
import zipfile
import numpy as np
from PIL import Image

# Добавляем backend в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ═══ Утилиты ═══

def make_jpeg_bytes(size=(64, 64), color=(255, 0, 0)):
    """Генерирует валидный JPEG в памяти."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return buf.getvalue()


def make_png_bytes(size=(64, 64), color=(0, 255, 0)):
    """Генерирует валидный PNG в памяти."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def make_webp_bytes(size=(64, 64), color=(0, 0, 255)):
    """Генерирует валидный WebP в памяти."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=85)
    buf.seek(0)
    return buf.getvalue()


def make_bmp_bytes(size=(64, 64), color=(128, 128, 0)):
    """Генерирует валидный BMP в памяти."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="BMP")
    buf.seek(0)
    return buf.getvalue()


def make_tiff_bytes(size=(64, 64), color=(0, 128, 128)):
    """Генерирует валидный TIFF в памяти."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="TIFF")
    buf.seek(0)
    return buf.getvalue()


def make_gif_bytes(size=(64, 64), color=(128, 0, 128)):
    """Генерирует валидный GIF в памяти."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="GIF")
    buf.seek(0)
    return buf.getvalue()


def make_fake_cr3_bytes():
    """Генерирует фейковый CR3 (RAW) файл — просто байты с заголовком."""
    # CR3 начинается с заголовка ftyp crx
    header = b'\x00\x00\x00\x1cftypcrx \x00\x00\x00\x00'
    payload = os.urandom(1024)  # 1KB фейковых данных
    return header + payload


def make_fake_raw_bytes():
    """Генерирует фейковый RAW файл."""
    return os.urandom(2048)


# ═══ Тесты сессий ═══

def test_create_session():
    """Создание сессии."""
    resp = client.post("/api/session/create")
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["status"] == "created"
    print(f"✓ create_session: id={data['session_id']}")


# ═══ Тесты загрузки эталонов (JPG) ═══

def test_upload_single_jpeg_reference():
    """Загрузка одного JPEG эталона."""
    resp = client.post("/api/session/create")
    sid = resp.json()["session_id"]

    jpeg = make_jpeg_bytes()
    resp = client.post(
        f"/api/upload/references/{sid}",
        files=[("files", ("ref1.jpg", jpeg, "image/jpeg"))]
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["saved"]) == 1
    assert data["total_refs"] == 1
    print(f"✓ upload_single_jpeg_ref: {data['saved']}")


def test_upload_multiple_jpeg_references():
    """Загрузка нескольких JPEG эталонов."""
    resp = client.post("/api/session/create")
    sid = resp.json()["session_id"]

    files = []
    for i in range(5):
        jpeg = make_jpeg_bytes(color=(i * 50, 100, 200))
        files.append(("files", (f"ref_{i}.jpg", jpeg, "image/jpeg")))

    resp = client.post(f"/api/upload/references/{sid}", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["saved"]) == 5
    assert data["total_refs"] == 5
    print(f"✓ upload_multiple_jpeg_refs: {data['total_refs']} файлов")


def test_upload_png_as_reference():
    """Загрузка PNG как эталона (расширение не проверяется)."""
    resp = client.post("/api/session/create")
    sid = resp.json()["session_id"]

    png = make_png_bytes()
    resp = client.post(
        f"/api/upload/references/{sid}",
        files=[("files", ("ref.png", png, "image/png"))]
    )
    assert resp.status_code == 200
    assert len(resp.json()["saved"]) == 1
    print("✓ upload_png_ref")


def test_upload_webp_as_reference():
    """Загрузка WebP как эталона."""
    resp = client.post("/api/session/create")
    sid = resp.json()["session_id"]

    webp = make_webp_bytes()
    resp = client.post(
        f"/api/upload/references/{sid}",
        files=[("files", ("ref.webp", webp, "image/webp"))]
    )
    assert resp.status_code == 200
    assert len(resp.json()["saved"]) == 1
    print("✓ upload_webp_ref")


# ═══ Тесты загрузки фото (RAW/CR3 и другие) ═══

def test_upload_single_cr3():
    """Загрузка одного CR3 файла."""
    resp = client.post("/api/session/create")
    sid = resp.json()["session_id"]

    cr3 = make_fake_cr3_bytes()
    resp = client.post(
        f"/api/upload/photos/{sid}",
        files=[("files", ("photo.CR3", cr3, "application/octet-stream"))]
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["saved"]) == 1
    assert data["total_photos"] == 1
    print(f"✓ upload_single_cr3: {data['saved']}")


def test_upload_multiple_cr3():
    """Загрузка нескольких CR3 файлов."""
    resp = client.post("/api/session/create")
    sid = resp.json()["session_id"]

    files = []
    for i in range(10):
        cr3 = make_fake_cr3_bytes()
        files.append(("files", (f"photo_{i:03d}.CR3", cr3, "application/octet-stream")))

    resp = client.post(f"/api/upload/photos/{sid}", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["saved"]) == 10
    assert data["total_photos"] == 10
    print(f"✓ upload_multiple_cr3: {data['total_photos']} файлов")


def test_upload_raw_variants():
    """Загрузка RAW файлов разных форматов (NEF, ARW, DNG, ORF, RW2)."""
    resp = client.post("/api/session/create")
    sid = resp.json()["session_id"]

    raw_formats = [
        ("photo.NEF", "Nikon"),
        ("photo.ARW", "Sony"),
        ("photo.DNG", "Adobe DNG"),
        ("photo.ORF", "Olympus"),
        ("photo.RW2", "Panasonic"),
        ("photo.RAF", "Fujifilm"),
        ("photo.PEF", "Pentax"),
        ("photo.CR2", "Canon old"),
    ]

    files = []
    for name, desc in raw_formats:
        raw = make_fake_raw_bytes()
        files.append(("files", (name, raw, "application/octet-stream")))

    resp = client.post(f"/api/upload/photos/{sid}", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["saved"]) == len(raw_formats)
    print(f"✓ upload_raw_variants: {len(raw_formats)} форматов ({', '.join(n for n, _ in raw_formats)})")


def test_upload_jpeg_as_photo():
    """Загрузка JPG файлов вместо RAW (должна работать — байты есть)."""
    resp = client.post("/api/session/create")
    sid = resp.json()["session_id"]

    jpeg = make_jpeg_bytes()
    resp = client.post(
        f"/api/upload/photos/{sid}",
        files=[("files", ("photo.jpg", jpeg, "image/jpeg"))]
    )
    assert resp.status_code == 200
    assert len(resp.json()["saved"]) == 1
    print("✓ upload_jpeg_as_photo")


def test_upload_png_as_photo():
    """Загрузка PNG файлов."""
    resp = client.post("/api/session/create")
    sid = resp.json()["session_id"]

    png = make_png_bytes()
    resp = client.post(
        f"/api/upload/photos/{sid}",
        files=[("files", ("photo.png", png, "image/png"))]
    )
    assert resp.status_code == 200
    assert len(resp.json()["saved"]) == 1
    print("✓ upload_png_as_photo")


def test_upload_tiff_as_photo():
    """Загрузка TIFF файлов."""
    resp = client.post("/api/session/create")
    sid = resp.json()["session_id"]

    tiff = make_tiff_bytes()
    resp = client.post(
        f"/api/upload/photos/{sid}",
        files=[("files", ("photo.tiff", tiff, "image/tiff"))]
    )
    assert resp.status_code == 200
    assert len(resp.json()["saved"]) == 1
    print("✓ upload_tiff_as_photo")


# ═══ Тесты статуса загрузки ═══

def test_upload_status():
    """Проверка статуса после загрузки."""
    resp = client.post("/api/session/create")
    sid = resp.json()["session_id"]

    # Грузим 2 эталона + 3 фото
    ref_files = [("files", (f"ref{i}.jpg", make_jpeg_bytes(), "image/jpeg")) for i in range(2)]
    client.post(f"/api/upload/references/{sid}", files=ref_files)

    photo_files = [("files", (f"p{i}.CR3", make_fake_cr3_bytes(), "application/octet-stream")) for i in range(3)]
    client.post(f"/api/upload/photos/{sid}", files=photo_files)

    resp = client.get(f"/api/upload/status/{sid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ref_count"] == 2
    assert data["photo_count"] == 3
    assert len(data["ref_files"]) == 2
    assert len(data["photo_files"]) == 3
    print(f"✓ upload_status: refs={data['ref_count']}, photos={data['photo_count']}")


def test_upload_status_invalid_session():
    """Статус несуществующей сессии → 404."""
    resp = client.get("/api/upload/status/nonexistent123")
    assert resp.status_code == 404
    print("✓ upload_status_invalid_session → 404")


# ═══ Тесты ошибок ═══

def test_upload_references_invalid_session():
    """Загрузка эталонов в несуществующую сессию → 404."""
    resp = client.post(
        "/api/upload/references/nonexistent",
        files=[("files", ("ref.jpg", make_jpeg_bytes(), "image/jpeg"))]
    )
    assert resp.status_code == 404
    print("✓ upload_refs_invalid_session → 404")


def test_upload_photos_invalid_session():
    """Загрузка фото в несуществующую сессию → 404."""
    resp = client.post(
        "/api/upload/photos/nonexistent",
        files=[("files", ("photo.CR3", make_fake_cr3_bytes(), "application/octet-stream"))]
    )
    assert resp.status_code == 404
    print("✓ upload_photos_invalid_session → 404")


# ═══ Тесты экспорта (download) ═══

def _create_analyzed_session():
    """Создаёт сессию с имитацией результатов анализа."""
    resp = client.post("/api/session/create")
    sid = resp.json()["session_id"]

    # Загружаем эталон
    client.post(
        f"/api/upload/references/{sid}",
        files=[("files", ("ref.jpg", make_jpeg_bytes(), "image/jpeg"))]
    )

    # Загружаем 3 "фото" (создаём реальные файлы)
    for i in range(3):
        cr3 = make_fake_cr3_bytes()
        client.post(
            f"/api/upload/photos/{sid}",
            files=[("files", (f"photo_{i}.cr3", cr3, "application/octet-stream"))]
        )

    # Имитируем результаты анализа (подменяем in-memory сессию)
    from app.services.session import get_session
    session = get_session(sid)
    session.status = "analyzed"
    session.results = [
        {"path": os.path.join(session.photo_dir, "photo_0.cr3"), "score": 0.95, "rank": 1, "accepted": True},
        {"path": os.path.join(session.photo_dir, "photo_1.cr3"), "score": 0.82, "rank": 2, "accepted": True},
        {"path": os.path.join(session.photo_dir, "photo_2.cr3"), "score": 0.45, "rank": 3, "accepted": False},
    ]

    return sid


def test_export_zip_accepted():
    """Скачивание ZIP с принятыми фото."""
    sid = _create_analyzed_session()

    resp = client.post(
        f"/api/export/{sid}/zip",
        json={"format": "jpg", "quality": 90, "include_rejected": False}
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"

    # Проверяем содержимое ZIP
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert "README.txt" in names
    accepted_files = [n for n in names if n.startswith("accepted/")]
    assert len(accepted_files) == 2  # только принятые
    print(f"✓ export_zip_accepted: {len(names)} файлов в ZIP ({len(accepted_files)} accepted)")


def test_export_zip_with_rejected():
    """Скачивание ZIP со всеми фото (включая отклонённые)."""
    sid = _create_analyzed_session()

    resp = client.post(
        f"/api/export/{sid}/zip",
        json={"format": "jpg", "quality": 90, "include_rejected": True}
    )
    assert resp.status_code == 200

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    accepted = [n for n in names if n.startswith("accepted/")]
    rejected = [n for n in names if n.startswith("rejected/")]
    assert len(accepted) == 2
    assert len(rejected) == 1
    print(f"✓ export_zip_all: accepted={len(accepted)}, rejected={len(rejected)}")


def test_export_json():
    """Скачивание JSON с результатами."""
    sid = _create_analyzed_session()

    resp = client.get(f"/api/export/{sid}/json")
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]

    data = json.loads(resp.content)
    assert data["total"] == 3
    assert data["accepted"] == 2
    assert len(data["results"]) == 3
    print(f"✓ export_json: total={data['total']}, accepted={data['accepted']}")


def test_export_zip_not_analyzed():
    """Экспорт ZIP до анализа → 400."""
    resp = client.post("/api/session/create")
    sid = resp.json()["session_id"]

    resp = client.post(
        f"/api/export/{sid}/zip",
        json={"format": "jpg", "quality": 90}
    )
    assert resp.status_code == 400
    print("✓ export_zip_not_analyzed → 400")


def test_export_json_not_analyzed():
    """Экспорт JSON до анализа → 400."""
    resp = client.post("/api/session/create")
    sid = resp.json()["session_id"]

    resp = client.get(f"/api/export/{sid}/json")
    assert resp.status_code == 400
    print("✓ export_json_not_analyzed → 400")


def test_export_zip_invalid_session():
    """Экспорт ZIP несуществующей сессии → 404."""
    resp = client.post(
        "/api/export/nonexistent/zip",
        json={"format": "jpg", "quality": 90}
    )
    assert resp.status_code == 404
    print("✓ export_zip_invalid_session → 404")


def test_export_json_invalid_session():
    """Экспорт JSON несуществующей сессии → 404."""
    resp = client.get("/api/export/nonexistent/json")
    assert resp.status_code == 404
    print("✓ export_json_invalid_session → 404")


# ═══ Тест API /models ═══

def test_list_models():
    """Получение списка моделей."""
    resp = client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    print(f"✓ list_models: {len(data['models'])} моделей")


# ═══ Тест health/root ═══

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    print("✓ health OK")


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "YouDo Photo" in resp.json()["name"]
    print("✓ root OK")


# ═══ Запуск ═══

if __name__ == "__main__":
    tests = [
        # Базовые
        test_health,
        test_root,
        test_list_models,
        # Сессии
        test_create_session,
        # Загрузка эталонов (разные форматы)
        test_upload_single_jpeg_reference,
        test_upload_multiple_jpeg_references,
        test_upload_png_as_reference,
        test_upload_webp_as_reference,
        # Загрузка фото (разные RAW форматы)
        test_upload_single_cr3,
        test_upload_multiple_cr3,
        test_upload_raw_variants,
        test_upload_jpeg_as_photo,
        test_upload_png_as_photo,
        test_upload_tiff_as_photo,
        # Статус
        test_upload_status,
        test_upload_status_invalid_session,
        # Ошибки
        test_upload_references_invalid_session,
        test_upload_photos_invalid_session,
        # Экспорт (скачивание)
        test_export_zip_accepted,
        test_export_zip_with_rejected,
        test_export_json,
        test_export_zip_not_analyzed,
        test_export_json_not_analyzed,
        test_export_zip_invalid_session,
        test_export_json_invalid_session,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Результат: {passed} ✅  {failed} ❌  из {len(tests)}")
