import cv2
import numpy as np
import os
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazy load model
_model = None


def get_model():
    global _model
    if _model is None:
        model_path = settings.MODEL_PATH
        logger.info(f"MODEL PATH IS {model_path}")
        if not os.path.exists(model_path):
            logger.warning(f"Model not found at {model_path}. Using demo mode.")
            return None
        try:
            from ultralytics import YOLO
            _model = YOLO(model_path)
            logger.info(f"Loaded YOLO model from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return None
    return _model


def demo_detect(frame: np.ndarray, frame_number: int) -> List[Dict]:
    """Generate fake detections for demo when no model is available."""
    import random
    detections = []
    h, w = frame.shape[:2]
    # Simulate occasional detections
    if random.random() > 0.7:
        label = random.choice(["fire", "smoke"])
        x1 = random.randint(0, w // 2)
        y1 = random.randint(0, h // 2)
        x2 = x1 + random.randint(50, 200)
        y2 = y1 + random.randint(50, 200)
        conf = random.uniform(0.45, 0.95)
        detections.append({
            "label": label,
            "confidence": conf,
            "bbox": [x1, y1, min(x2, w), min(y2, h)],
        })
    return detections


def detect_frame(frame: np.ndarray) -> List[Dict]:
    """Run YOLOv8 detection on a single frame."""
    model = get_model()
    if model is None:
        return []  # handled by caller

    try:
        results = model(
            frame,
            conf=settings.CONFIDENCE_THRESHOLD,
            iou=settings.IOU_THRESHOLD,
            verbose=False,
        )
        detections = []
        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                label = result.names[cls_id]
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append({
                    "label": label,
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2],
                })
        return detections
    except Exception as e:
        logger.error(f"Detection error: {e}")
        return []


def draw_detections(frame: np.ndarray, detections: List[Dict]) -> np.ndarray:
    """Draw bounding boxes and labels on frame."""
    COLORS = {
        "fire": (0, 0, 255),    # BGR: Red
        "smoke": (128, 128, 128),  # Grey
    }
    DEFAULT_COLOR = (0, 165, 255)  # Orange

    for det in detections:
        label = det["label"]
        conf = det["confidence"]
        bbox = det["bbox"]
        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        color = COLORS.get(label.lower(), DEFAULT_COLOR)

        # Draw box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Draw label background
        text = f"{label} {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 6, y1), color, -1)
        cv2.putText(frame, text, (x1 + 3, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    return frame


def process_video(
    input_path: str,
    output_path: str,
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Process video with fire/smoke detection.
    Returns summary dict with all detections.
    """
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {input_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    use_demo = get_model() is None
    if use_demo:
        logger.warning("Model not loaded — using DEMO detection mode")

    all_detections = []
    frame_number = 0
    frames_processed = 0
    start_time = time.time()
    frame_skip = settings.FRAME_SKIP

    # Timeline: frame -> detections
    timeline = {}

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_number % frame_skip == 0:
            if use_demo:
                dets = demo_detect(frame, frame_number)
            else:
                dets = detect_frame(frame)

            timestamp = frame_number / fps if fps > 0 else 0

            if dets:
                timeline[str(frame_number)] = {
                    "timestamp": timestamp,
                    "detections": dets,
                }
                for d in dets:
                    all_detections.append({
                        "frame_number": frame_number,
                        "timestamp": timestamp,
                        **d,
                    })

            # Draw on frame
            annotated = draw_detections(frame.copy(), dets)
            frames_processed += 1

            if progress_callback:
                pct = (frame_number / total_frames * 100) if total_frames > 0 else 0
                progress_callback(
                    progress=pct,
                    current_frame=frame_number,
                    total_frames=total_frames,
                    detections_found=len(all_detections),
                )
        else:
            annotated = frame

        out.write(annotated)
        frame_number += 1

    cap.release()
    out.release()

    processing_time = time.time() - start_time

    # Compute summary
    fire_count = sum(1 for d in all_detections if "fire" in d["label"].lower())
    smoke_count = sum(1 for d in all_detections if "smoke" in d["label"].lower())
    confidences = [d["confidence"] for d in all_detections]
    timestamps = [d["timestamp"] for d in all_detections]

    if fire_count > 0 and smoke_count > 0:
        overall_label = "fire_and_smoke"
    elif fire_count > 0:
        overall_label = "fire"
    elif smoke_count > 0:
        overall_label = "smoke"
    else:
        overall_label = "none"

    return {
        "all_detections": all_detections,
        "total_detections": len(all_detections),
        "fire_detections": fire_count,
        "smoke_detections": smoke_count,
        "max_confidence": max(confidences) if confidences else None,
        "avg_confidence": sum(confidences) / len(confidences) if confidences else None,
        "first_detection_time": min(timestamps) if timestamps else None,
        "last_detection_time": max(timestamps) if timestamps else None,
        "overall_label": overall_label,
        "frames_processed": frames_processed,
        "processing_time": processing_time,
        "fps": fps,
        "width": width,
        "height": height,
        "total_frames": total_frames,
        "duration": duration,
        "timeline": timeline,
    }