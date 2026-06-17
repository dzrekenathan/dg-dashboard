import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import AsyncSessionLocal
from app.models import ActivityTracking, ActivityComment, Task as TaskModel
from app.schemas import (
    ActivityTrackingOut, ActivityTrackingUpdate,
    ActivityCommentCreate, ActivityCommentOut, RecentCommentOut,
)
from app.core.security import get_current_user

router = APIRouter(prefix="/activity-tracking", tags=["activity-tracking"])


async def get_db():
    async with AsyncSessionLocal() as db:
        yield db


def _to_out(tracking, comments):
    return ActivityTrackingOut(
        id=tracking.id,
        task_id=tracking.task_id,
        activity_ref=tracking.activity_ref,
        status=tracking.status,
        assigned_to=tracking.assigned_to,
        progress_pct=tracking.progress_pct,
        target_date=tracking.target_date,
        comments=[
            ActivityCommentOut(
                id=c.id,
                author_name=c.author_name,
                content=c.content,
                created_at=c.created_at.isoformat(),
            )
            for c in comments
        ],
    )


async def _get_comments(db, tracking_id):
    return (
        await db.execute(
            select(ActivityComment)
            .where(ActivityComment.tracking_id == tracking_id)
            .order_by(ActivityComment.created_at)
        )
    ).scalars().all()


@router.get("/stats")
async def get_activity_stats(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    total_comments = (
        await db.execute(select(func.count()).select_from(ActivityComment))
    ).scalar_one()
    return {"total_comments": total_comments}


@router.get("/recent", response_model=list[RecentCommentOut])
async def get_recent_comments(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = (
        select(
            ActivityComment.id,
            ActivityComment.author_name,
            ActivityComment.content,
            ActivityComment.created_at,
            ActivityTracking.task_id,
            ActivityTracking.activity_ref,
            TaskModel.so_number,
            TaskModel.thematic_area,
            TaskModel.task,
        )
        .join(ActivityTracking, ActivityComment.tracking_id == ActivityTracking.id)
        .join(TaskModel, ActivityTracking.task_id == TaskModel.id)
        .order_by(ActivityComment.created_at.desc())
        .limit(20)
    )
    rows = (await db.execute(stmt)).all()
    return [
        RecentCommentOut(
            id=row.id,
            author_name=row.author_name,
            content=row.content,
            created_at=row.created_at.isoformat(),
            task_id=row.task_id,
            activity_ref=row.activity_ref,
            so_number=row.so_number,
            thematic_area=row.thematic_area,
            task_name=row.task,
        )
        for row in rows
    ]


@router.get("/{task_id}", response_model=list[ActivityTrackingOut])
async def get_task_activity_tracking(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    rows = (
        await db.execute(select(ActivityTracking).where(ActivityTracking.task_id == task_id))
    ).scalars().all()

    return [_to_out(t, await _get_comments(db, t.id)) for t in rows]


@router.patch("/{task_id}/{activity_ref:path}", response_model=ActivityTrackingOut)
async def upsert_activity_tracking(
    task_id: str,
    activity_ref: str,
    body: ActivityTrackingUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    tracking = (
        await db.execute(
            select(ActivityTracking).where(
                ActivityTracking.task_id == task_id,
                ActivityTracking.activity_ref == activity_ref,
            )
        )
    ).scalar_one_or_none()

    if not tracking:
        tracking = ActivityTracking(
            id=str(uuid.uuid4()),
            task_id=task_id,
            activity_ref=activity_ref,
            status=body.status or "Not Started",
            assigned_to=body.assigned_to or "",
            progress_pct=body.progress_pct or 0,
            target_date=body.target_date or "",
        )
        db.add(tracking)
    else:
        if body.status is not None:
            tracking.status = body.status
        if body.assigned_to is not None:
            tracking.assigned_to = body.assigned_to
        if body.progress_pct is not None:
            tracking.progress_pct = body.progress_pct
        if body.target_date is not None:
            tracking.target_date = body.target_date

    await db.commit()
    await db.refresh(tracking)
    return _to_out(tracking, await _get_comments(db, tracking.id))


@router.post("/{task_id}/{activity_ref:path}/comments", response_model=ActivityTrackingOut)
async def add_activity_comment(
    task_id: str,
    activity_ref: str,
    body: ActivityCommentCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    tracking = (
        await db.execute(
            select(ActivityTracking).where(
                ActivityTracking.task_id == task_id,
                ActivityTracking.activity_ref == activity_ref,
            )
        )
    ).scalar_one_or_none()

    if not tracking:
        tracking = ActivityTracking(
            id=str(uuid.uuid4()),
            task_id=task_id,
            activity_ref=activity_ref,
            status="Not Started",
            assigned_to="",
        )
        db.add(tracking)
        await db.flush()

    db.add(ActivityComment(
        id=str(uuid.uuid4()),
        tracking_id=tracking.id,
        author_name=body.author_name or user.name,
        content=body.content,
    ))
    await db.commit()
    await db.refresh(tracking)
    return _to_out(tracking, await _get_comments(db, tracking.id))
