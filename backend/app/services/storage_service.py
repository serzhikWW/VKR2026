import os
import io
import logging
from pathlib import Path
from minio.error import S3Error
from app.core.minio_client import minio_client, get_presigned_url
from app.core.config import settings

logger = logging.getLogger(__name__)


def upload_video(file_path: str, object_name: str) -> bool:
    """Upload a video file to MinIO."""
    try:
        minio_client.fput_object(
            settings.MINIO_BUCKET_VIDEOS,
            object_name,
            file_path,
            content_type="video/mp4",
        )
        logger.info(f"Uploaded video: {object_name}")
        return True
    except S3Error as e:
        logger.error(f"Failed to upload video {object_name}: {e}")
        return False


def upload_result_video(file_path: str, object_name: str) -> bool:
    """Upload processed video to results bucket."""
    try:
        minio_client.fput_object(
            settings.MINIO_BUCKET_RESULTS,
            object_name,
            file_path,
            content_type="video/mp4",
        )
        logger.info(f"Uploaded result video: {object_name}")
        return True
    except S3Error as e:
        logger.error(f"Failed to upload result video {object_name}: {e}")
        return False


def download_video(object_name: str, dest_path: str) -> bool:
    """Download a video from MinIO to local path."""
    try:
        minio_client.fget_object(
            settings.MINIO_BUCKET_VIDEOS,
            object_name,
            dest_path,
        )
        return True
    except S3Error as e:
        logger.error(f"Failed to download video {object_name}: {e}")
        return False


def get_video_url(object_name: str) -> str:
    return get_presigned_url(settings.MINIO_BUCKET_VIDEOS, object_name)


def get_result_url(object_name: str) -> str:
    return get_presigned_url(settings.MINIO_BUCKET_RESULTS, object_name)


def delete_video(object_name: str):
    try:
        minio_client.remove_object(settings.MINIO_BUCKET_VIDEOS, object_name)
    except S3Error as e:
        logger.error(f"Failed to delete video {object_name}: {e}")


def delete_result(object_name: str):
    try:
        minio_client.remove_object(settings.MINIO_BUCKET_RESULTS, object_name)
    except S3Error as e:
        logger.error(f"Failed to delete result {object_name}: {e}")
