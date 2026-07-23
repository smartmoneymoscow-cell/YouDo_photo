FROM python:3.12-slim

# ffmpeg для извлечения кадров из видео
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY server.py .
COPY frontend/ frontend/
COPY requirements-render.txt requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p uploads

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
