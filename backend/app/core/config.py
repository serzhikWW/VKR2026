from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://fireuser:firepass@localhost:5432/firedetection"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin123"
    MINIO_BUCKET_VIDEOS: str = "videos"
    MINIO_BUCKET_RESULTS: str = "results"
    MINIO_SECURE: bool = False
    REDIS_URL: str = "redis://localhost:6379"
    # Путь внутри контейнера — backend/models/ монтируется в /app/models/
    MODEL_PATH: str = "/app/models/yolo26s.pt"
    SECRET_KEY: str = "supersecretkey123"
    TEMP_DIR: str = "/tmp/fire_detection"
    CONFIDENCE_THRESHOLD: float = 0.25
    IOU_THRESHOLD: float = 0.45
    FRAME_SKIP: int = 2

    # ── Live RTSP streaming ───────────────────────────────────────────────
    # Force TCP for RTSP — much more reliable over the network than UDP
    RTSP_TRANSPORT: str = "tcp"
    # Socket timeout for OpenCV/FFmpeg in microseconds (5 s)
    RTSP_OPEN_TIMEOUT_US: int = 5_000_000
    # Maximum number of simultaneous live streams
    MAX_LIVE_STREAMS: int = 4
    # Run detection on every Nth frame for live mode (saves CPU/GPU)
    LIVE_FRAME_SKIP: int = 2
    # JPEG quality for MJPEG output (1-100)
    LIVE_JPEG_QUALITY: int = 75
    # How many recent detections to keep in memory per stream
    LIVE_DETECTION_HISTORY: int = 50

    class Config:
        env_file = ".env"


settings = Settings()