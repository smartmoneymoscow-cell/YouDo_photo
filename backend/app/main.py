"""YouDo Photo — Backend API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import upload, process

app = FastAPI(
    title="YouDo Photo API",
    description="ИИ-обработка интерьерных фотографий",
    version="0.1.0",
)

# CORS — allow GitHub Pages frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://smartmoneymoscow-cell.github.io",
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(upload.router)
app.include_router(process.router)


@app.get("/")
async def root():
    return {
        "name": "YouDo Photo API",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
