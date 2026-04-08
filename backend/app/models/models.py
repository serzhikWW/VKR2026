from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class VideoStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DetectionLabel(str, enum.Enum):
    FIRE = "fire"
    SMOKE = "smoke"
    FIRE_AND_SMOKE = "fire_and_smoke"
    NONE = "none"


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    minio_object = Column(String(512), nullable=False)  # path in MinIO
    minio_bucket = Column(String(255), nullable=False)
    file_size = Column(Integer)
    duration = Column(Float)  # seconds
    fps = Column(Float)
    width = Column(Integer)
    height = Column(Integer)
    total_frames = Column(Integer)
    status = Column(Enum(VideoStatus), default=VideoStatus.UPLOADED, nullable=False)
    task_id = Column(String(255))  # Celery task ID
    error_message = Column(Text)
    processed_video_object = Column(String(512))  # annotated video in MinIO
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    detections = relationship("Detection", back_populates="video", cascade="all, delete-orphan")
    summary = relationship("DetectionSummary", back_populates="video", uselist=False, cascade="all, delete-orphan")


class Detection(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    frame_number = Column(Integer, nullable=False)
    timestamp = Column(Float, nullable=False)  # seconds from start
    label = Column(String(50), nullable=False)  # fire, smoke
    confidence = Column(Float, nullable=False)
    bbox_x1 = Column(Float)
    bbox_y1 = Column(Float)
    bbox_x2 = Column(Float)
    bbox_y2 = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="detections")


class DetectionSummary(Base):
    __tablename__ = "detection_summaries"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, unique=True)
    total_detections = Column(Integer, default=0)
    fire_detections = Column(Integer, default=0)
    smoke_detections = Column(Integer, default=0)
    max_confidence = Column(Float)
    avg_confidence = Column(Float)
    first_detection_time = Column(Float)  # seconds
    last_detection_time = Column(Float)
    overall_label = Column(Enum(DetectionLabel), default=DetectionLabel.NONE)
    frames_processed = Column(Integer, default=0)
    processing_time = Column(Float)  # seconds
    stats_json = Column(JSON)  # timeline data
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    video = relationship("Video", back_populates="summary")
