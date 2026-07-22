#!/bin/bash
# Запуск YouDo Photo (бэкенд + фронтенд)
# ========================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════════╗"
echo "║       YouDo Photo v2 — AI-отбор фото     ║"
echo "╚══════════════════════════════════════════╝"

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден"
    exit 1
fi

# Установка зависимостей (если нужно)
if [ "$1" = "--install" ]; then
    echo "📦 Установка зависимостей..."
    pip3 install -r "$SCRIPT_DIR/backend/requirements.txt"
    echo "✅ Зависимости установлены"
fi

# Создание директории для загрузок
mkdir -p "$SCRIPT_DIR/backend/uploads"

# Запуск бэкенда
echo ""
echo "🚀 Запуск API на http://localhost:8000"
echo "📂 Загрузки: $SCRIPT_DIR/backend/uploads"
echo ""

cd "$SCRIPT_DIR"
python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# Если хотите фронтенд отдельно (nginx/python http.server):
# cd "$SCRIPT_DIR/frontend"
# python3 -m http.server 3000 &
# echo "🌐 Фронтенд: http://localhost:3000"
