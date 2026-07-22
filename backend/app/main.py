"""YouDo Photo — Backend API с AI-отбором по эмбеддингам."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import upload, analyze, export

app = FastAPI(
    title="YouDo Photo API",
    description="ИИ-обработка интерьерных фотографий по сходству с эталоном",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api")
app.include_router(analyze.router, prefix="/api")
app.include_router(export.router, prefix="/api")


@app.get("/")
async def root():
    return {"name": "YouDo Photo API", "version": "2.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "ok"}
