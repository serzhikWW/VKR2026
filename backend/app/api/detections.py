from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional, List

from app.core.database import get_db
from app.models.models import Detection, DetectionSummary
from app.schemas.schemas import DetectionResponse, DetectionSummaryResponse

router = APIRouter()


@router.get("/video/{video_id}", response_model=List[DetectionResponse])
async def get_video_detections(
    video_id: int,
    label: Optional[str] = None,
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get detections for a specific video."""
    query = select(Detection).where(
        Detection.video_id == video_id,
        Detection.confidence >= min_confidence,
    ).order_by(Detection.frame_number)

    if label:
        query = query.where(Detection.label == label)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/summary/{video_id}", response_model=DetectionSummaryResponse)
async def get_detection_summary(video_id: int, db: AsyncSession = Depends(get_db)):
    """Get detection summary for a video."""
    result = await db.execute(
        select(DetectionSummary).where(DetectionSummary.video_id == video_id)
    )
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(404, "Summary not found")
    return summary


@router.get("/stats/overview")
async def get_overview_stats(db: AsyncSession = Depends(get_db)):
    """Get overall system statistics."""
    from sqlalchemy import func
    from app.models.models import Video, VideoStatus

    total_videos = (await db.execute(select(func.count(Video.id)))).scalar()
    completed = (await db.execute(
        select(func.count(Video.id)).where(Video.status == VideoStatus.COMPLETED)
    )).scalar()
    processing = (await db.execute(
        select(func.count(Video.id)).where(Video.status == VideoStatus.PROCESSING)
    )).scalar()
    failed = (await db.execute(
        select(func.count(Video.id)).where(Video.status == VideoStatus.FAILED)
    )).scalar()

    fire_count = (await db.execute(
        select(func.sum(DetectionSummary.fire_detections))
    )).scalar() or 0
    smoke_count = (await db.execute(
        select(func.sum(DetectionSummary.smoke_detections))
    )).scalar() or 0

    return {
        "total_videos": total_videos,
        "completed": completed,
        "processing": processing,
        "failed": failed,
        "total_fire_detections": fire_count,
        "total_smoke_detections": smoke_count,
    }
