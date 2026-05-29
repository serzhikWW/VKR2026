import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis
from app.core.config import settings
from app.services.stream_service import stream_manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/progress/{video_id}")
async def video_progress_ws(websocket: WebSocket, video_id: int):
    """WebSocket endpoint for real-time processing progress."""
    await websocket.accept()
    logger.info(f"WebSocket connected for video {video_id}")

    r = None
    pubsub = None
    try:
        r = await aioredis.from_url(settings.REDIS_URL)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"video_progress:{video_id}")

        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=1.0,
                )
                if message and message["type"] == "message":
                    data = json.loads(message["data"])
                    await websocket.send_json(data)

                    # Close if done
                    if data.get("status") in ("completed", "failed"):
                        await asyncio.sleep(0.5)
                        break

                # Send heartbeat
                await websocket.send_json({"type": "heartbeat", "video_id": video_id})
                await asyncio.sleep(0.5)

            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break
            except Exception as e:
                logger.error(f"WS error for video {video_id}: {e}")
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for video {video_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe(f"video_progress:{video_id}")
            except Exception:
                pass
        if r:
            await r.close()
        logger.info(f"WebSocket closed for video {video_id}")


@router.websocket("/streams/{stream_id}")
async def live_stream_stats_ws(websocket: WebSocket, stream_id: str):
    """WebSocket endpoint streaming live RTSP stats and recent detections."""
    await websocket.accept()
    logger.info(f"Live stream WS connected: {stream_id}")
    try:
        while True:
            stream = stream_manager.get(stream_id)
            if not stream:
                await websocket.send_json({"type": "error", "message": "stream_not_found"})
                break

            data = stream.to_dict()
            data["type"] = "stats"
            await websocket.send_json(data)

            if stream.status not in ("starting", "running"):
                # Send a final frame and bail out
                await asyncio.sleep(0.5)
                break

            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        logger.info(f"Live stream WS disconnected: {stream_id}")
    except Exception as e:
        logger.error(f"Live stream WS error [{stream_id}]: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
