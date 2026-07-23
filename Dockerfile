FROM python:3.11-slim

# System deps: ffmpeg for video, libraw for RAW conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libraw-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy core (AI models)
COPY core/ core/

# Copy backend app
COPY backend/app/ backend/app/

# Copy frontend
COPY frontend/ frontend/

# Pre-download default model weights (OpenCLIP ViT-L/14)
RUN python -c "\
import open_clip; \
model, _, preprocess = open_clip.create_model_and_transforms('ViT-L-14', pretrained='laion2b_s32b_b82k'); \
print('Model cached OK')"

# Create uploads directory
RUN mkdir -p uploads

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
