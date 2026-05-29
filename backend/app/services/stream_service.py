"""
Live RTSP stream service.

Each LiveStream runs in a background daemon thread, pulls frames from an
RTSP source via OpenCV/FFmpeg, runs YOLO detection on every Nth frame and
keeps the latest annotated JPEG frame + detection stats in memory so they
can be served via an MJPEG endpoint and a WebSocket.

This module is intentionally self-contained so it can live next to the
existing detection_service without affecting the offline-video pipeline.
"""

import os
import cv2
import time
import uuid
import logging
import threading
from collections import deque
from typing import Dict, List, Optional, Any

from app.core.config import settings
from app.services.detection_service import (
    detect_frame,
    demo_detect,
    draw_detections,
    get_model,
)

logger = logging.getLogger(__name__)


class LiveStream:
    """A single RTSP source being processed in a background thread."""

    def __init__(self, stream_id: str, rtsp_url: str, name: Optional[str] = None):
        self.id = stream_id
        self.rtsp_url = rtsp_url
        self.name = name or f"Поток {stream_id[:6]}"

        # State
        self.status = "starting"  # starting | running | stopped | error
        self.error_message: Optional[str] = None
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.stopped_at: Optional[float] = None

        # Frame buffer (latest annotated JPEG)
        self._latest_jpeg: Optional[bytes] = None
        self._frame_lock = threading.Lock()
        self._frame_event = threading.Event()

        # Stats
        self.frames_total = 0
        self.frames_processed = 0
        self.detections_total = 0
        self.fire_total = 0
        self.smoke_total = 0
        self.current_fps = 0.0
        self.width: Optional[int] = None
        self.height: Optional[int] = None
        self.source_fps: Optional[float] = None
        self.last_detection_at: Optional[float] = None

        # Recent detections ring buffer (for the UI log)
        self.recent_detections: deque = deque(maxlen=settings.LIVE_DETECTION_HISTORY)

        # Thread control
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── Public API ────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"live-stream-{self.id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        self.status = "stopped"
        self.stopped_at = time.time()
        self._frame_event.set()  # release any blocked readers

    def get_latest_jpeg(self, timeout: float = 1.0) -> Optional[bytes]:
        """Block until a new frame is available or `timeout` elapses."""
        self._frame_event.wait(timeout=timeout)
        with self._frame_lock:
            jpeg = self._latest_jpeg
            self._frame_event.clear()
        return jpeg

    def to_dict(self) -> Dict[str, Any]:
        uptime = None
        if self.started_at:
            end = self.stopped_at or time.time()
            uptime = round(end - self.started_at, 1)

        return {
            "id": self.id,
            "name": self.name,
            "rtsp_url": self.rtsp_url,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "uptime_seconds": uptime,
            "width": self.width,
            "height": self.height,
            "source_fps": self.source_fps,
            "current_fps": round(self.current_fps, 2),
            "frames_total": self.frames_total,
            "frames_processed": self.frames_processed,
            "detections_total": self.detections_total,
            "fire_total": self.fire_total,
            "smoke_total": self.smoke_total,
            "last_detection_at": self.last_detection_at,
            "recent_detections": list(self.recent_detections),
        }

    # ── Background worker ────────────────────────────────────────────────

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        # Force FFmpeg backend with the configured transport (tcp by default).
        # This must be set BEFORE constructing the VideoCapture.
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            f"rtsp_transport;{settings.RTSP_TRANSPORT}"
            f"|stimeout;{settings.RTSP_OPEN_TIMEOUT_US}"
        )
        try:
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        except Exception as e:
            logger.error(f"[stream {self.id}] VideoCapture exception: {e}")
            return None

        if not cap.isOpened():
            logger.error(f"[stream {self.id}] Failed to open RTSP: {self.rtsp_url}")
            return None

        # Keep the internal buffer small so we always work with fresh frames
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or None
        self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or None
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        self.source_fps = src_fps if src_fps > 0 else None
        return cap

    def _run(self) -> None:
        logger.info(f"[stream {self.id}] starting RTSP capture: {self.rtsp_url}")
        cap = self._open_capture()
        if cap is None:
            self.status = "error"
            self.error_message = "Не удалось подключиться к RTSP источнику"
            return

        self.status = "running"
        self.started_at = time.time()

        use_demo = get_model() is None
        if use_demo:
            logger.warning(f"[stream {self.id}] YOLO model not loaded — demo mode")

        last_fps_t = time.time()
        last_fps_count = 0
        frame_index = 0
        consecutive_failures = 0
        MAX_FAILURES = 30

        try:
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures > MAX_FAILURES:
                        logger.error(
                            f"[stream {self.id}] too many read failures, aborting"
                        )
                        self.status = "error"
                        self.error_message = "Поток прерван (нет кадров от источника)"
                        break
                    time.sleep(0.05)
                    continue
                consecutive_failures = 0
                self.frames_total += 1

                # Run detection only every Nth frame
                run_detect = (frame_index % max(1, settings.LIVE_FRAME_SKIP)) == 0
                detections: List[Dict[str, Any]] = []
                if run_detect:
                    try:
                        if use_demo:
                            detections = demo_detect(frame, frame_index)
                        else:
                            detections = detect_frame(frame)
                    except Exception as e:
                        logger.error(f"[stream {self.id}] detect error: {e}")
                        detections = []
                    self.frames_processed += 1

                    if detections:
                        ts = time.time()
                        self.last_detection_at = ts
                        self.detections_total += len(detections)
                        for d in detections:
                            label_lc = (d.get("label") or "").lower()
                            if "fire" in label_lc:
                                self.fire_total += 1
                            if "smoke" in label_lc:
                                self.smoke_total += 1
                            self.recent_detections.append({
                                "timestamp": ts,
                                "frame_number": self.frames_total,
                                "label": d.get("label"),
                                "confidence": round(float(d.get("confidence", 0)), 3),
                                "bbox": [round(float(x), 1) for x in d.get("bbox", [])],
                            })

                # Always draw the latest known boxes on the frame
                annotated = draw_detections(frame.copy(), detections) if detections else frame

                # Encode and publish
                ok_enc, buf = cv2.imencode(
                    ".jpg",
                    annotated,
                    [int(cv2.IMWRITE_JPEG_QUALITY), int(settings.LIVE_JPEG_QUALITY)],
                )
                if ok_enc:
                    with self._frame_lock:
                        self._latest_jpeg = buf.tobytes()
                    self._frame_event.set()

                # FPS counter (rolling, updated every second)
                now = time.time()
                if now - last_fps_t >= 1.0:
                    self.current_fps = (self.frames_total - last_fps_count) / (now - last_fps_t)
                    last_fps_t = now
                    last_fps_count = self.frames_total

                frame_index += 1

        except Exception as e:
            logger.error(f"[stream {self.id}] worker crashed: {e}", exc_info=True)
            self.status = "error"
            self.error_message = str(e)
        finally:
            try:
                cap.release()
            except Exception:
                pass
            if self.status == "running":
                self.status = "stopped"
            self.stopped_at = time.time()
            self._frame_event.set()
            logger.info(
                f"[stream {self.id}] worker exited "
                f"(frames={self.frames_total}, detections={self.detections_total})"
            )


class StreamManager:
    """Process-wide registry of active live streams (thread-safe)."""

    def __init__(self) -> None:
        self._streams: Dict[str, LiveStream] = {}
        self._lock = threading.Lock()

    def create(self, rtsp_url: str, name: Optional[str] = None) -> LiveStream:
        with self._lock:
            active = sum(1 for s in self._streams.values() if s.status in ("starting", "running"))
            if active >= settings.MAX_LIVE_STREAMS:
                raise RuntimeError(
                    f"Достигнут лимит активных потоков ({settings.MAX_LIVE_STREAMS})"
                )
            stream_id = uuid.uuid4().hex[:12]
            stream = LiveStream(stream_id, rtsp_url, name=name)
            self._streams[stream_id] = stream
        stream.start()
        return stream

    def get(self, stream_id: str) -> Optional[LiveStream]:
        with self._lock:
            return self._streams.get(stream_id)

    def list(self) -> List[LiveStream]:
        with self._lock:
            return list(self._streams.values())

    def stop(self, stream_id: str) -> bool:
        with self._lock:
            stream = self._streams.get(stream_id)
        if not stream:
            return False
        stream.stop()
        return True

    def remove(self, stream_id: str) -> bool:
        with self._lock:
            stream = self._streams.pop(stream_id, None)
        if not stream:
            return False
        stream.stop()
        return True

    def shutdown_all(self) -> None:
        with self._lock:
            streams = list(self._streams.values())
            self._streams.clear()
        for s in streams:
            try:
                s.stop()
            except Exception:
                pass


# Singleton used by the API layer
stream_manager = StreamManager()
