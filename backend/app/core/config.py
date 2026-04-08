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
    MODEL_PATH: str = "/app/models/best.pt"
    SECRET_KEY: str = "supersecretkey123"
    TEMP_DIR: str = "/tmp/fire_detection"
    CONFIDENCE_THRESHOLD: float = 0.25
    IOU_THRESHOLD: float = 0.45
    FRAME_SKIP: int = 2

    class Config:
        env_file = ".env"


settings = Settings()