import os
import asyncio
import logging
import tempfile
from celery import Celery
from app.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "fire_detection",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


def publish_progress(video_id: int, progress: float, current_frame: int,
                     total_frames: int, detections_found: int, status: str = "processing"):
    """Publish progress via Redis pub/sub for WebSocket."""
    import redis
    import json
    r = redis.from_url(settings.REDIS_URL)
    data = {
        "video_id": video_id,
        "progress": progress,
        "current_frame": current_frame,
        "total_frames": total_frames,
        "detections_found": detections_found,
        "status": status,
    }
    r.publish(f"video_progress:{video_id}", json.dumps(data))


@celery_app.task(bind=True, name="process_video_task")
def process_video_task(self, video_id: int, minio_object: str, original_filename: str):
    """Main Celery task: download, process, upload, save to DB."""
    import redis
    import json
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.models import Video, Detection, DetectionSummary, VideoStatus, DetectionLabel
    from app.services.detection_service import process_video
    from app.services.storage_service import download_video, upload_result_video

    # Sync DB engine for Celery
    sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    tmp_input = None
    tmp_output = None

    try:
        # Update status to processing
        video = session.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")

        video.status = VideoStatus.PROCESSING
        video.task_id = self.request.id
        session.commit()

        publish_progress(video_id, 0, 0, 0, 0, "processing")

        # Download from MinIO
        os.makedirs(settings.TEMP_DIR, exist_ok=True)
        tmp_input = os.path.join(settings.TEMP_DIR, f"input_{video_id}.mp4")
        tmp_output = os.path.join(settings.TEMP_DIR, f"output_{video_id}.mp4")

        logger.info(f"Downloading video {video_id} from MinIO...")
        success = download_video(minio_object, tmp_input)
        if not success:
            raise RuntimeError("Failed to download video from MinIO")

        # Process video with YOLO
        logger.info(f"Processing video {video_id}...")

        def on_progress(progress, current_frame, total_frames, detections_found):
            publish_progress(video_id, progress, current_frame, total_frames, detections_found)

        result = process_video(tmp_input, tmp_output, progress_callback=on_progress)

        # Update video metadata
        video.fps = result["fps"]
        video.width = result["width"]
        video.height = result["height"]
        video.total_frames = result["total_frames"]
        video.duration = result["duration"]

        # Upload processed video
        result_object = f"processed_{video_id}_{original_filename}"
        upload_result_video(tmp_output, result_object)
        video.processed_video_object = result_object

        # Save detections (batch insert)
        detection_objects = []
        for det in result["all_detections"]:
            bbox = det.get("bbox", [None, None, None, None])
            d = Detection(
                video_id=video_id,
                frame_number=det["frame_number"],
                timestamp=det["timestamp"],
                label=det["label"],
                confidence=det["confidence"],
                bbox_x1=bbox[0] if len(bbox) > 0 else None,
                bbox_y1=bbox[1] if len(bbox) > 1 else None,
                bbox_x2=bbox[2] if len(bbox) > 2 else None,
                bbox_y2=bbox[3] if len(bbox) > 3 else None,
            )
            detection_objects.append(d)

        if detection_objects:
            session.bulk_save_objects(detection_objects)

        # Determine overall label enum
        label_map = {
            "fire": DetectionLabel.FIRE,
            "smoke": DetectionLabel.SMOKE,
            "fire_and_smoke": DetectionLabel.FIRE_AND_SMOKE,
            "none": DetectionLabel.NONE,
        }
        overall = label_map.get(result["overall_label"], DetectionLabel.NONE)

        # Save summary
        existing_summary = session.query(DetectionSummary).filter(
            DetectionSummary.video_id == video_id
        ).first()

        if existing_summary:
            summary = existing_summary
        else:
            summary = DetectionSummary(video_id=video_id)
            session.add(summary)

        summary.total_detections = result["total_detections"]
        summary.fire_detections = result["fire_detections"]
        summary.smoke_detections = result["smoke_detections"]
        summary.max_confidence = result["max_confidence"]
        summary.avg_confidence = result["avg_confidence"]
        summary.first_detection_time = result["first_detection_time"]
        summary.last_detection_time = result["last_detection_time"]
        summary.overall_label = overall
        summary.frames_processed = result["frames_processed"]
        summary.processing_time = result["processing_time"]
        summary.stats_json = {"timeline": result["timeline"]}

        video.status = VideoStatus.COMPLETED
        session.commit()

        publish_progress(video_id, 100, result["total_frames"],
                         result["total_frames"], result["total_detections"], "completed")
        logger.info(f"Video {video_id} processed successfully: {result['total_detections']} detections")

    except Exception as e:
        logger.error(f"Error processing video {video_id}: {e}", exc_info=True)
        try:
            video = session.query(Video).filter(Video.id == video_id).first()
            if video:
                from app.models.models import VideoStatus
                video.status = VideoStatus.FAILED
                video.error_message = str(e)
                session.commit()
        except Exception:
            pass
        publish_progress(video_id, 0, 0, 0, 0, "failed")
        raise
    finally:
        session.close()
        # Cleanup temp files
        for f in [tmp_input, tmp_output]:
            if f and os.path.exists(f):
                os.remove(f)
