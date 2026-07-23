FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libraw-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install torch CPU-only first
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install the rest from PyPI
RUN pip install --no-cache-dir \
    fastapi uvicorn python-multipart python-dotenv \
    rawpy numpy opencv-python-headless Pillow \
    open-clip-torch psutil

COPY core/ core/
COPY backend/ backend/
COPY frontend/ frontend/

RUN mkdir -p uploads

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
