#!/bin/bash
set -e

echo "=== YouDo Photo v2 Starting ==="
echo "Python: $(python3 --version)"
echo "Working dir: $(pwd)"
echo "Files: $(ls -la)"

# Test imports
echo "=== Testing imports ==="
python3 -c "import fastapi; print(f'fastapi: {fastapi.__version__}')"
python3 -c "import uvicorn; print(f'uvicorn: {uvicorn.__version__}')"

echo "=== Starting uvicorn ==="
exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1
