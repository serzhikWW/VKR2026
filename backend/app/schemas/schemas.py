from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.models import VideoStatus, DetectionLabel


class VideoBase(BaseModel):
    original_filename: str


class VideoCreate(VideoBase):
    pass


class VideoResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_size: Optional[int]
    duration: Optional[float]
    fps: Optional[float]
    width: Optional[int]
    height: Optional[int]
    total_frames: Optional[int]
    status: VideoStatus
    task_id: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    video_url: Optional[str] = None
    processed_video_url: Optional[str] = None

    class Config:
        from_attributes = True


class DetectionBase(BaseModel):
    frame_number: int
    timestamp: float
    label: str
    confidence: float
    bbox_x1: Optional[float]
    bbox_y1: Optional[float]
    bbox_x2: Optional[float]
    bbox_y2: Optional[float]


class DetectionResponse(DetectionBase):
    id: int
    video_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class DetectionSummaryResponse(BaseModel):
    id: int
    video_id: int
    total_detections: int
    fire_detections: int
    smoke_detections: int
    max_confidence: Optional[float]
    avg_confidence: Optional[float]
    first_detection_time: Optional[float]
    last_detection_time: Optional[float]
    overall_label: DetectionLabel
    frames_processed: int
    processing_time: Optional[float]
    stats_json: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class VideoDetailResponse(VideoResponse):
    summary: Optional[DetectionSummaryResponse] = None
    detections_count: int = 0

    class Config:
        from_attributes = True


class ProcessingProgress(BaseModel):
    video_id: int
    task_id: str
    status: VideoStatus
    progress: float = 0.0  # 0-100
    current_frame: int = 0
    total_frames: int = 0
    detections_found: int = 0
    message: str = ""


class PaginatedVideos(BaseModel):
    items: List[VideoResponse]
    total: int
    page: int
    size: int
    pages: int
