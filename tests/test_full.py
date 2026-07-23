"""Полные интеграционные тесты YouDo Photo (server.py)."""

import io
import os
import json
import time
import zipfile
import struct
import requests
from PIL import Image

BASE = "http://localhost:8000"
passed = 0
failed = 0


def ok(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✅ {name}" + (f" ({detail})" if detail else ""))
    else:
        failed += 1
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


def make_jpeg(w=64, h=64, color=(200, 50, 50)):
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return buf.getvalue()


def make_png(w=64, h=64, color=(50, 200, 50)):
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def make_webp(w=64, h=64, color=(50, 50, 200)):
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=85)
    buf.seek(0)
    return buf.getvalue()


def make_tiff(w=64, h=64, color=(128, 128, 0)):
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="TIFF")
    buf.seek(0)
    return buf.getvalue()


def make_bmp(w=64, h=64, color=(0, 128, 128)):
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="BMP")
    buf.seek(0)
    return buf.getvalue()


def make_gif(w=64, h=64, color=(128, 0, 128)):
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="GIF")
    buf.seek(0)
    return buf.getvalue()


def make_fake_cr3():
    header = b'\x00\x00\x00\x1cftypcrx \x00\x00\x00\x00'
    return header + os.urandom(1024)


def make_fake_raw():
    return os.urandom(2048)


def make_small_video(seconds=2):
    """Создаёт короткое тестовое видео через ffmpeg."""
    import subprocess
    path = "/tmp/test_video.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"color=c=blue:size=320x240:duration={seconds}:rate=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        path, "-hide_banner", "-loglevel", "error"
    ], check=True)
    with open(path, "rb") as f:
        return f.read()


# ═══════════════════════════════════════════
print("\n═══ 1. HEALTH & ROOT ═══")

r = requests.get(f"{BASE}/health")
ok("GET /health", r.status_code == 200 and r.json()["status"] == "ok")

r = requests.get(f"{BASE}/")
ok("GET /", r.status_code == 200 and "YouDo Photo" in r.text)

r = requests.get(f"{BASE}/api/models")
ok("GET /api/models", r.status_code == 200 and "histogram_demo" in r.json())

# ═══════════════════════════════════════════
print("\n═══ 2. СОЗДАНИЕ СЕССИЙ ═══")

r = requests.post(f"{BASE}/api/session/create")
ok("POST /api/session/create", r.status_code == 200)
sid = r.json()["session_id"]
ok("session_id exists", len(sid) == 12, f"id={sid}")


# ═══════════════════════════════════════════
print("\n═══ 3. ЗАГРУЗКА ЭТАЛОНОВ (все форматы) ═══")

for fmt, maker, ext, mime in [
    ("JPEG", make_jpeg, "jpg", "image/jpeg"),
    ("PNG",  make_png,  "png", "image/png"),
    ("WebP", make_webp, "webp", "image/webp"),
    ("TIFF", make_tiff, "tiff", "image/tiff"),
    ("BMP",  make_bmp,  "bmp", "image/bmp"),
    ("GIF",  make_gif,  "gif", "image/gif"),
]:
    r2 = requests.post(f"{BASE}/api/session/create")
    sid2 = r2.json()["session_id"]
    data = maker()
    r3 = requests.post(
        f"{BASE}/api/upload/references/{sid2}",
        files=[("files", (f"ref.{ext}", data, mime))]
    )
    ok(f"upload ref {fmt}", r3.status_code == 200 and r3.json()["total_refs"] == 1)


# ═══════════════════════════════════════════
print("\n═══ 4. ЗАГРУЗКА ФОТО (все форматы) ═══")

r2 = requests.post(f"{BASE}/api/session/create")
sid_photo = r2.json()["session_id"]

for fmt, maker, ext, mime in [
    ("JPEG", make_jpeg, "jpg", "image/jpeg"),
    ("PNG",  make_png,  "png", "image/png"),
    ("WebP", make_webp, "webp", "image/webp"),
    ("TIFF", make_tiff, "tiff", "image/tiff"),
    ("BMP",  make_bmp,  "bmp", "image/bmp"),
    ("GIF",  make_gif,  "gif", "image/gif"),
]:
    r3 = requests.post(
        f"{BASE}/api/upload/photos/{sid_photo}",
        files=[("files", (f"photo.{ext}", maker(), mime))]
    )
    ok(f"upload photo {fmt}", r3.status_code == 200)

# RAW форматы
for ext, desc in [("cr3","Canon"), ("cr2","Canon old"), ("nef","Nikon"), ("arw","Sony"),
                   ("dng","Adobe"), ("orf","Olympus"), ("rw2","Panasonic"), ("raf","Fujifilm"),
                   ("pef","Pentax"), ("raw","Generic")]:
    r3 = requests.post(
        f"{BASE}/api/upload/photos/{sid_photo}",
        files=[("files", (f"photo.{ext}", make_fake_cr3(), "application/octet-stream"))]
    )
    ok(f"upload photo .{ext} ({desc})", r3.status_code == 200)

print(f"  📊 Итого фото в сессии: {r3.json()['total_photos']}")


# ═══════════════════════════════════════════
print("\n═══ 5. ЗАГРУЗКА ВИДЕО + ИЗВЛЕЧЕНИЕ КАДРОВ ═══")

# Сначала эталон
r2 = requests.post(f"{BASE}/api/session/create")
sid_vid = r2.json()["session_id"]
requests.post(
    f"{BASE}/api/upload/references/{sid_vid}",
    files=[("files", ("ref.jpg", make_jpeg(), "image/jpeg"))]
)

# Видео
vid_data = make_small_video(seconds=2)
r4 = requests.post(
    f"{BASE}/api/upload/video/{sid_vid}?fps=1&max_frames=5",
    files=[("files", ("test.mp4", vid_data, "video/mp4"))]
)
ok("upload video mp4", r4.status_code == 200, f"frames={r4.json().get('extracted_frames', 0)}")
ok("video frames > 0", r4.json().get("extracted_frames", 0) > 0,
   f"{r4.json().get('extracted_frames')} frames")

# Проверяем что кадры добавились как фото
ok("video frames as photos", r4.json().get("total_photos", 0) > 0,
   f"total_photos={r4.json().get('total_photos')}")


# ═══════════════════════════════════════════
print("\n═══ 6. СТАТУС ЗАГРУЗКИ ═══")

r5 = requests.get(f"{BASE}/api/upload/status/{sid_photo}")
ok("GET upload/status", r5.status_code == 200)
d = r5.json()
ok("status has ref_count", d.get("ref_count", 0) == 0, "no refs in photo session")
ok("status has photo_count", d.get("photo_count", 0) > 0, f"{d.get('photo_count')} photos")

r5b = requests.get(f"{BASE}/api/upload/status/nonexistent")
ok("status nonexistent → 404", r5b.status_code == 404)


# ═══════════════════════════════════════════
print("\n═══ 7. ОШИБКИ ЗАГРУЗКИ ═══")

r6 = requests.post(f"{BASE}/api/upload/references/nonexistent",
                    files=[("files", ("r.jpg", make_jpeg(), "image/jpeg"))])
ok("refs nonexistent → 404", r6.status_code == 404)

r7 = requests.post(f"{BASE}/api/upload/photos/nonexistent",
                    files=[("files", ("p.cr3", make_fake_cr3(), "application/octet-stream"))])
ok("photos nonexistent → 404", r7.status_code == 404)

r7b = requests.post(f"{BASE}/api/upload/video/nonexistent",
                     files=[("files", ("v.mp4", vid_data, "video/mp4"))])
ok("video nonexistent → 404", r7b.status_code == 404)


# ═══════════════════════════════════════════
print("\n═══ 8. АНАЛИЗ ═══")

# Сессия с JPEG эталонами + JPEG фото
r8 = requests.post(f"{BASE}/api/session/create")
sid_analysis = r8.json()["session_id"]

for i in range(3):
    requests.post(
        f"{BASE}/api/upload/references/{sid_analysis}",
        files=[("files", (f"ref{i}.jpg", make_jpeg(color=(200, 100, 50)), "image/jpeg"))]
    )

for i in range(5):
    requests.post(
        f"{BASE}/api/upload/photos/{sid_analysis}",
        files=[("files", (f"photo{i}.jpg", make_jpeg(color=(200+i*5, 100+i*3, 50+i*2)), "image/jpeg"))]
    )

r9 = requests.post(f"{BASE}/api/analyze/{sid_analysis}", json={
    "model": "histogram_demo",
    "threshold": 0.5,
    "top_k": 0,
})
ok("POST analyze", r9.status_code == 200, f"elapsed={r9.json().get('elapsed_sec')}s")
ok("analyze results exist", r9.json().get("total", 0) == 5)
ok("analyze has accepted", r9.json().get("accepted_count", 0) >= 0)
ok("analyze has model", r9.json().get("model") == "histogram_demo")

# Анализ без эталонов
r9b = requests.post(f"{BASE}/api/session/create")
sid_no_ref = r9b.json()["session_id"]
requests.post(
    f"{BASE}/api/upload/photos/{sid_no_ref}",
    files=[("files", ("p.jpg", make_jpeg(), "image/jpeg"))]
)
r9c = requests.post(f"{BASE}/api/analyze/{sid_no_ref}", json={"threshold": 0.75})
ok("analyze no refs → 400", r9c.status_code == 400)

# Анализ без фото
r9d = requests.post(f"{BASE}/api/session/create")
sid_no_photo = r9d.json()["session_id"]
requests.post(
    f"{BASE}/api/upload/references/{sid_no_photo}",
    files=[("files", ("r.jpg", make_jpeg(), "image/jpeg"))]
)
r9e = requests.post(f"{BASE}/api/analyze/{sid_no_photo}", json={"threshold": 0.75})
ok("analyze no photos → 400", r9e.status_code == 400)


# ═══════════════════════════════════════════
print("\n═══ 9. АНАЛИЗ С ВИДЕО ═══")

r9f = requests.post(f"{BASE}/api/analyze/{sid_vid}", json={"threshold": 0.5})
ok("analyze video session", r9f.status_code == 200, f"total={r9f.json().get('total')}")
ok("video frames analyzed", r9f.json().get("total", 0) > 0)


# ═══════════════════════════════════════════
print("\n═══ 10. ЭКСПОРТ ZIP ═══")

r10 = requests.post(f"{BASE}/api/export/{sid_analysis}/zip")
ok("POST export/zip", r10.status_code == 200)
ok("zip content-type", "application/zip" in r10.headers.get("content-type", ""))

zf = zipfile.ZipFile(io.BytesIO(r10.content))
names = zf.namelist()
ok("zip has README.txt", "README.txt" in names)
ok("zip has accepted/", any(n.startswith("accepted/") for n in names), f"{len(names)} files")

# ZIP до анализа
r10b = requests.post(f"{BASE}/api/session/create")
sid_no_analysis = r10b.json()["session_id"]
r10c = requests.post(f"{BASE}/api/export/{sid_no_analysis}/zip")
ok("zip not analyzed → 400", r10c.status_code == 400)

# ZIP nonexistent
r10d = requests.post(f"{BASE}/api/export/nonexistent/zip")
ok("zip nonexistent → 404", r10d.status_code == 404)


# ═══════════════════════════════════════════
print("\n═══ 11. ЭКСПОРТ JSON ═══")

r11 = requests.get(f"{BASE}/api/export/{sid_analysis}/json")
ok("GET export/json", r11.status_code == 200)
ok("json content-type", "application/json" in r11.headers.get("content-type", ""))

jdata = json.loads(r11.content)
ok("json has results", len(jdata.get("results", [])) == 5)
ok("json has accepted count", jdata.get("accepted", 0) >= 0)

# JSON до анализа
r11b = requests.get(f"{BASE}/api/export/{sid_no_analysis}/json")
ok("json not analyzed → 400", r11b.status_code == 400)

# JSON nonexistent
r11c = requests.get(f"{BASE}/api/export/nonexistent/json")
ok("json nonexistent → 404", r11c.status_code == 404)


# ═══════════════════════════════════════════
print(f"\n{'═'*50}")
print(f"  ИТОГО: {passed} ✅   {failed} ❌   из {passed + failed}")
print(f"{'═'*50}")
