from minio import Minio
from minio.error import S3Error
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)


async def init_minio():
    """Create buckets if they don't exist."""
    for bucket in [settings.MINIO_BUCKET_VIDEOS, settings.MINIO_BUCKET_RESULTS]:
        try:
            if not minio_client.bucket_exists(bucket):
                minio_client.make_bucket(bucket)
                logger.info(f"Created bucket: {bucket}")
            else:
                logger.info(f"Bucket already exists: {bucket}")
        except S3Error as e:
            logger.error(f"MinIO error for bucket {bucket}: {e}")


def get_minio():
    return minio_client


def get_presigned_url(bucket: str, object_name: str, expires_seconds: int = 3600) -> str:
    from datetime import timedelta
    try:
        url = minio_client.presigned_get_object(
            bucket, object_name, expires=timedelta(seconds=expires_seconds)
        )
        return url
    except S3Error as e:
        logger.error(f"Error generating presigned URL: {e}")
        return ""
