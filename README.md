# YouDo Photo v2 — AI-отбор интерьерных фотографий

Полный пайплайн: загрузка CR3/RAW → AI-эмбеддинги → сравнение с эталоном → отбор лучших кадров.

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│  ФРОНТЕНД (HTML/CSS/JS)                                      │
│  4-шаговый wizard:                                           │
│  1. Загрузка (CR3/RAW + JPG-эталоны)                         │
│  2. Параметры (модель, порог, top-K)                          │
│  3. Модерация (галерея с AI-скорами, ручная проверка)         │
│  4. Экспорт (ZIP / JSON)                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────────────┐
│  БЭКЕНД (FastAPI)                                            │
│                                                              │
│  /api/session/create     — создать сессию                    │
│  /api/upload/references  — загрузить эталоны                 │
│  /api/upload/photos      — загрузить CR3/RAW                 │
│  /api/analyze/{id}       — AI-анализ (эмбеддинги + сравнение)│
│  /api/export/{id}/zip    — экспорт в ZIP                     │
│  /api/export/{id}/json   — экспорт в JSON                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  AI-ЯДРО (core/)                                             │
│                                                              │
│  raw_reader.py   — RawTherapee / dcraw / rawpy конвертация   │
│  embedding.py    — OpenCLIP / CLIP / DINOv2 / ResNet50       │
│  similarity.py   — косинусное сходство / FAISS поиск         │
│  pipeline.py     — оркестрация всех этапов                   │
└─────────────────────────────────────────────────────────────┘
```

## Быстрый старт

```bash
# 1. Установить зависимости
pip install -r backend/requirements.txt

# 2. Запустить
chmod +x start.sh
./start.sh

# 3. Открыть http://localhost:8000
```

## Структура проекта

```
youdo_photo_embed/
├── start.sh                    # Скрипт запуска
├── README.md
│
├── core/                       # AI-ядро (используется бэкендом)
│   ├── raw_reader.py           # Чтение CR3/RAW (RawTherapee/dcraw/rawpy)
│   ├── embedding.py            # Извлечение эмбеддингов
│   ├── similarity.py           # Сравнение + FAISS
│   └── pipeline.py             # Полный пайплайн
│
├── backend/                    # FastAPI сервер
│   ├── requirements.txt
│   ├── uploads/                # Загруженные файлы (auto)
│   └── app/
│       ├── main.py             # Точка входа API
│       ├── routes/
│       │   ├── upload.py       # Загрузка файлов
│       │   ├── analyze.py      # AI-анализ
│       │   └── export.py       # Экспорт ZIP/JSON
│       └── services/
│           ├── session.py      # Управление сессиями
│           └── analyzer.py     # Обёртка над core/
│
├── frontend/                   # Веб-интерфейс
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
│
├── run.py                      # CLI (без сервера)
├── requirements.txt
└── tests/
    └── test_pipeline.py
```

## API Endpoints

| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/session/create` | Создать сессию |
| POST | `/api/upload/references/{id}` | Загрузить эталоны (multipart) |
| POST | `/api/upload/photos/{id}` | Загрузить CR3/RAW (multipart) |
| GET | `/api/upload/status/{id}` | Статус загрузки |
| POST | `/api/analyze/{id}` | Запустить AI-анализ |
| GET | `/api/analyze/{id}/results` | Получить результаты |
| GET | `/api/models` | Список моделей |
| POST | `/api/export/{id}/zip` | Скачать ZIP |
| GET | `/api/export/{id}/json` | Скачать JSON |

## Модели

| Модель | Размер | RAM | Качество | Авто |
|---|---|---|---|---|
| **CLIP ViT-B/32** | 512-d | ~400 MB | ★★★★ | ✅ default |
| ResNet50 | 2048-d | ~250 MB | ★★★ | fallback |
| OpenCLIP ViT-L/14 | 768-d | ~1.5 GB | ★★★★★ | RAM ≥ 2GB |
| DINOv2 ViT-S/14 | 384-d | ~400 MB | ★★★★ | ручной |

## CLI (без сервера)

```bash
python run.py --ref reference.jpg --photos-dir ./photos/ --threshold 0.75
python run.py --ref ref.jpg --photos-dir ./cr3/ --model openclip_vit_l14 --top-k 10
```
