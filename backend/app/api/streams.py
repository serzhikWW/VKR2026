"""
REST + streaming API for live RTSP detection.

Endpoints:
    POST   /api/streams/                  → start a new live stream
    GET    /api/streams/                  → list all streams
    GET    /api/streams/{stream_id}       → stream info + recent detections
    POST   /api/streams/{stream_id}/stop  → stop the stream (keeps record)
    DELETE /api/streams/{stream_id}       → stop and remove the stream
    GET    /api/streams/{stream_id}/mjpeg → live MJPEG video (multipart)
"""

import asyncio
import logging
from typing import List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.schemas.schemas import StreamCreate, StreamResponse
from app.services.stream_service import stream_manager, LiveStream

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────

def _to_response(s: LiveStream) -> StreamResponse:
    data = s.to_dict()
    data["mjpeg_url"] = f"/api/streams/{s.id}/mjpeg"
    return StreamResponse(**data)


# ── REST endpoints ────────────────────────────────────────────────────────

@router.post("/", response_model=StreamResponse)
async def create_stream(payload: StreamCreate):
    url = (payload.rtsp_url or "").strip()
    if not url:
        raise HTTPException(400, "RTSP URL не может быть пустым")
    if not (
        url.startswith("rtsp://")
        or url.startswith("rtsps://")
        or url.startswith("http://")
        or url.startswith("https://")
    ):
        raise HTTPException(
            400, "Поддерживаются только rtsp://, rtsps://, http(s):// источники"
        )

    try:
        stream = stream_manager.create(url, name=payload.name)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        logger.error(f"create_stream failed: {e}", exc_info=True)
        raise HTTPException(500, f"Ошибка запуска потока: {e}")

    # Give the worker thread a moment to attempt connection so the response
    # already reflects "running" or "error".
    await asyncio.sleep(0.5)
    return _to_response(stream)


@router.get("/", response_model=List[StreamResponse])
async def list_streams():
    return [_to_response(s) for s in stream_manager.list()]


@router.get("/{stream_id}", response_model=StreamResponse)
async def get_stream(stream_id: str):
    stream = stream_manager.get(stream_id)
    if not stream:
        raise HTTPException(404, "Поток не найден")
    return _to_response(stream)


@router.post("/{stream_id}/stop", response_model=StreamResponse)
async def stop_stream(stream_id: str):
    stream = stream_manager.get(stream_id)
    if not stream:
        raise HTTPException(404, "Поток не найден")
    stream.stop()
    return _to_response(stream)


@router.delete("/{stream_id}")
async def delete_stream(stream_id: str):
    if not stream_manager.remove(stream_id):
        raise HTTPException(404, "Поток не найден")
    return {"message": "Поток остановлен и удалён"}


# ── MJPEG live video ──────────────────────────────────────────────────────

BOUNDARY = "frame"


@router.get("/{stream_id}/mjpeg")
async def mjpeg_feed(stream_id: str, request: Request):
    """Multipart MJPEG stream for direct embedding into <img src>."""
    stream = stream_manager.get(stream_id)
    if not stream:
        raise HTTPException(404, "Поток не найден")

    async def generator():
        loop = asyncio.get_running_loop()
        try:
            while True:
                if await request.is_disconnected():
                    break
                if stream.status not in ("starting", "running"):
                    break

                jpeg = await loop.run_in_executor(None, stream.get_latest_jpeg, 1.0)
                if jpeg is None:
                    # No frame yet; let the client keep waiting
                    await asyncio.sleep(0.05)
                    continue

                yield (
                    b"--" + BOUNDARY.encode() + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
                    + jpeg + b"\r\n"
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"mjpeg generator error [{stream_id}]: {e}")

    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Connection": "close",
    }
    return StreamingResponse(
        generator(),
        media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
        headers=headers,
    )
