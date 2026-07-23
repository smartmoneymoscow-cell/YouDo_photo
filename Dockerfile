FROM python:3.11-slim

# System deps: ffmpeg for video, libraw for RAW conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libraw-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Limit thread parallelism to save memory (critical for free tier)
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV PYTHONUNBUFFERED=1

# Copy requirements first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy core (AI models)
COPY core/ core/

# Copy backend app
COPY backend/app/ backend/app/

# Copy frontend
COPY frontend/ frontend/

# Pre-download CLIP ViT-B/32 (~350MB, fits in 512MB RAM)
RUN python -c "\
import open_clip; \
model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s347b_k799e'); \
print('CLIP ViT-B/32 cached OK')"

# Create uploads directory
RUN mkdir -p uploads

EXPOSE 8000

# --preload: load model once at startup (shared across workers)
# --workers 1: single worker to avoid duplicating model in memory
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--preload", "--workers", "1"]
