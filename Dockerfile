FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libraw-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

# Single pip install: use PyPI + PyTorch CPU index together
RUN pip install --no-cache-dir \
    -r requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu

COPY core/ core/
COPY backend/app/ backend/app/
COPY frontend/ frontend/

# Pre-download CLIP ViT-B/32
RUN python -c "\
import open_clip; \
open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s347b_k799e'); \
print('OK')"

RUN mkdir -p uploads

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--preload", "--workers", "1"]
