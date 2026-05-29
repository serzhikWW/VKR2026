import os
import uuid
import logging
import math
import asyncio
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional

from app.core.database import get_db
from app.core.config import settings
from app.core.minio_client import minio_client
from app.models.models import Video, Detection, DetectionSummary, VideoStatus
from app.schemas.schemas import VideoResponse, VideoDetailResponse, PaginatedVideos
from app.services.storage_service import upload_video, delete_video, delete_result
from app.worker import process_video_task

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_TYPES = {
    "video/mp4", "video/avi", "video/mov", "video/mkv",
    "video/webm", "video/x-msvideo", "video/quicktime",
}
MAX_FILE_SIZE = 500 * 1024 * 1024

# ── Static / fixed routes MUST come before /{video_id} catch-all ──────────────

@router.post("/upload", response_model=VideoResponse)
async def upload_video_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Invalid file type: {file.content_type}")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large (max 500 MB)")

    ext = os.path.splitext(file.filename)[1] or ".mp4"
    unique_name = f"{uuid.uuid4().hex}{ext}"

    os.makedirs(settings.TEMP_DIR, exist_ok=True)
    tmp_path = os.path.join(settings.TEMP_DIR, unique_name)
    with open(tmp_path, "wb") as f:
        f.write(contents)

    minio_object = f"videos/{unique_name}"
    success = upload_video(tmp_path, minio_object)
    os.remove(tmp_path)

    if not success:
        raise HTTPException(500, "Failed to upload video to storage")

    video = Video(
        filename=unique_name,
        original_filename=file.filename,
        minio_object=minio_object,
        minio_bucket=settings.MINIO_BUCKET_VIDEOS,
        file_size=len(contents),
        status=VideoStatus.UPLOADED,
    )
    db.add(video)
    await db.flush()
    await db.refresh(video)

    task = process_video_task.delay(video.id, minio_object, unique_name)
    video.task_id = task.id
    await db.commit()
    await db.refresh(video)

    return _video_to_response(video)


@router.get("/", response_model=PaginatedVideos)
async def list_videos(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    status: Optional[VideoStatus] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Video).order_by(desc(Video.created_at))
    count_query = select(func.count(Video.id))
    if status:
        query = query.where(Video.status == status)
        count_query = count_query.where(Video.status == status)

    total = (await db.execute(count_query)).scalar()
    offset = (page - 1) * size
    result = await db.execute(query.offset(offset).limit(size))
    videos = result.scalars().all()

    return PaginatedVideos(
        items=[_video_to_response(v) for v in videos],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 1,
    )


# ── Parametric routes ──────────────────────────────────────────────────────────

@router.get("/{video_id}/stream/result")
async def stream_result_video(
    video_id: int,
    request: Request,
    download: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Stream processed/annotated video with Range support."""
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(404, "Video not found")
    if not video.processed_video_object:
        raise HTTPException(404, "Processed video not ready yet")

    return await _build_stream_response(
        bucket=settings.MINIO_BUCKET_RESULTS,
        obj_name=video.processed_video_object,
        request=request,
        filename=f"annotated_{video.original_filename}",
        download=download,
    )


@router.get("/{video_id}/stream")
async def stream_video(
    video_id: int,
    request: Request,
    download: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Stream original video with Range support."""
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(404, "Video not found")

    return await _build_stream_response(
        bucket=settings.MINIO_BUCKET_VIDEOS,
        obj_name=video.minio_object,
        request=request,
        filename=video.original_filename,
        download=download,
    )


@router.get("/{video_id}", response_model=VideoDetailResponse)
async def get_video(video_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(404, "Video not found")

    summary_result = await db.execute(
        select(DetectionSummary).where(DetectionSummary.video_id == video_id)
    )
    summary = summary_result.scalar_one_or_none()

    count_result = await db.execute(
        select(func.count(Detection.id)).where(Detection.video_id == video_id)
    )
    detections_count = count_result.scalar()

    resp = _video_to_response(video)
    return VideoDetailResponse(
        **resp.model_dump(),
        summary=summary,
        detections_count=detections_count,
    )


@router.delete("/{video_id}")
async def delete_video_record(video_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(404, "Video not found")

    if video.minio_object:
        delete_video(video.minio_object)
    if video.processed_video_object:
        delete_result(video.processed_video_object)

    await db.delete(video)
    await db.commit()
    return {"message": "Video deleted"}


# ── Streaming helper ───────────────────────────────────────────────────────────

async def _build_stream_response(
    bucket: str,
    obj_name: str,
    request: Request,
    filename: str,
    download: bool = False,
) -> StreamingResponse:
    from minio.error import S3Error

    loop = asyncio.get_running_loop()  # correct way in async context

    # 1. Get object size
    try:
        stat = await loop.run_in_executor(
            None, lambda: minio_client.stat_object(bucket, obj_name)
        )
        total_size = stat.size
    except Exception as e:
        logger.error(f"stat_object failed [{bucket}/{obj_name}]: {e}")
        raise HTTPException(404, f"File not found in storage: {obj_name}")

    # 2. Parse Range header
    range_header = request.headers.get("range", "").strip()
    start, end = 0, total_size - 1

    if range_header and range_header.startswith("bytes="):
        try:
            parts = range_header[6:].split("-")
            start = int(parts[0])
            end = int(parts[1]) if parts[1].strip() else total_size - 1
        except Exception:
            start, end = 0, total_size - 1

    start = max(0, min(start, total_size - 1))
    end   = max(start, min(end, total_size - 1))
    length = end - start + 1

    content_type = _guess_content_type(obj_name)
    disposition = "attachment" if download else "inline"

    # HTTP headers must be latin-1; use RFC 5987 for non-latin filenames (e.g. Cyrillic)
    from urllib.parse import quote as _quote
    _disp = "attachment" if download else "inline"
    try:
        filename.encode("latin-1")
        _cd = _disp + '; filename="' + filename + '"'
    except (UnicodeEncodeError, UnicodeDecodeError):
        _enc = _quote(filename, safe="")
        _fb = filename.encode("ascii", errors="ignore").decode("ascii") or "video.mp4"
        _cd = _disp + '; filename="' + _fb + '"; filename*=UTF-8\'\'' + _enc
    headers = {
        "Accept-Ranges":  "bytes",
        "Content-Length": str(length),
        "Content-Disposition": _cd,
        "Cache-Control":  "no-cache",
    }
    if range_header:
        headers["Content-Range"] = f"bytes {start}-{end}/{total_size}"

    status_code = 206 if range_header else 200

    # 3. Fetch the byte range once, stream it in chunks
    #    We do the blocking get_object in the executor, then read in chunks
    CHUNK = 256 * 1024  # 256 KB

    async def streamer():
        try:
            resp_obj = await loop.run_in_executor(
                None,
                lambda: minio_client.get_object(bucket, obj_name, offset=start, length=length)
            )
        except Exception as e:
            logger.error(f"get_object failed [{bucket}/{obj_name}] offset={start} length={length}: {e}")
            return

        try:
            while True:
                chunk = await loop.run_in_executor(None, lambda: resp_obj.read(CHUNK))
                if not chunk:
                    break
                yield chunk
        except Exception as e:
            logger.error(f"Streaming read error: {e}")
        finally:
            try:
                resp_obj.close()
                resp_obj.release_conn()
            except Exception:
                pass

    return StreamingResponse(
        streamer(),
        status_code=status_code,
        headers=headers,
        media_type=content_type,
    )


def _guess_content_type(obj_name: str) -> str:
    name = obj_name.lower()
    if   name.endswith(".mp4"):  return "video/mp4"
    elif name.endswith(".webm"): return "video/webm"
    elif name.endswith(".avi"):  return "video/x-msvideo"
    elif name.endswith(".mov"):  return "video/quicktime"
    elif name.endswith(".mkv"):  return "video/x-matroska"
    return "video/mp4"


def _video_to_response(video: Video) -> VideoResponse:
    video_url     = f"/api/videos/{video.id}/stream"        if video.minio_object            else None
    processed_url = f"/api/videos/{video.id}/stream/result" if video.processed_video_object  else None
    return VideoResponse(
        id=video.id,
        filename=video.filename,
        original_filename=video.original_filename,
        file_size=video.file_size,
        duration=video.duration,
        fps=video.fps,
        width=video.width,
        height=video.height,
        total_frames=video.total_frames,
        status=video.status,
        task_id=video.task_id,
        error_message=video.error_message,
        created_at=video.created_at,
        updated_at=video.updated_at,
        video_url=video_url,
        processed_video_url=processed_url,
    )