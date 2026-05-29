from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.database import engine, Base
from app.core.minio_client import init_minio
from app.api import videos, detections, websocket, streams
from app.services.stream_service import stream_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Fire Detection API...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await init_minio()
    logger.info("Startup complete.")
    yield
    logger.info("Shutting down...")
    try:
        stream_manager.shutdown_all()
    except Exception as e:
        logger.error(f"Stream manager shutdown error: {e}")
    await engine.dispose()


app = FastAPI(
    title="Fire & Smoke Detection API",
    description="Real-time fire and smoke detection using YOLOv8",
    version="1.0.0",
    lifespan=lifespan,
)

# allow_credentials=True is incompatible with allow_origins=["*"]
# Use explicit origins or set credentials to False
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length", "Content-Disposition"],
)

app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(detections.router, prefix="/api/detections", tags=["detections"])
app.include_router(streams.router, prefix="/api/streams", tags=["streams"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "fire-detection-api"}