import io
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import ChecklistItem, ChecklistComment, User, UserRole
from app.schemas import (
    ChecklistItemOut, ChecklistItemUpdate,
    ChecklistCommentOut, ChecklistCommentCreate, RecentChecklistCommentOut,
)
from app.core.security import get_current_user
from app.core.ws_manager import manager

router = APIRouter(prefix="/checklist", tags=["checklist"])


def _staff_directorate_filter(user: User) -> Optional[str]:
    """Staff are confined to their own directorate; other roles see everything."""
    if user.role == UserRole.STAFF:
        return user.directorate.value if user.directorate else "__none__"
    return None


def _assert_can_touch_item(user: User, item: ChecklistItem) -> None:
    if user.role == UserRole.STAFF and item.directorate != (user.directorate.value if user.directorate else None):
        raise HTTPException(status_code=403, detail="Not authorised for this directorate's checklist")


@router.get("", response_model=list[ChecklistItemOut])
async def list_checklist(
    section_number: Optional[int] = Query(None),
    directorate: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(ChecklistItem).order_by(ChecklistItem.item_order)
    if section_number is not None:
        stmt = stmt.where(ChecklistItem.section_number == section_number)
    staff_directorate = _staff_directorate_filter(user)
    if staff_directorate is not None:
        stmt = stmt.where(ChecklistItem.directorate == staff_directorate)
    elif directorate:
        stmt = stmt.where(ChecklistItem.directorate == directorate)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/stats")
async def checklist_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(ChecklistItem).order_by(ChecklistItem.item_order))
    items = result.scalars().all()

    total = len(items)
    completed = sum(1 for i in items if i.status == "Completed")
    in_progress = sum(1 for i in items if i.status == "In Progress")
    at_risk = sum(1 for i in items if i.status == "At Risk")

    sections: dict = {}
    for item in items:
        sn = item.section_number
        if sn not in sections:
            sections[sn] = {
                "section_number": sn,
                "section_title": item.section_title,
                "directorate": item.directorate,
                "total": 0, "completed": 0, "in_progress": 0, "at_risk": 0,
            }
        sections[sn]["total"] += 1
        if item.status == "Completed":
            sections[sn]["completed"] += 1
        elif item.status == "In Progress":
            sections[sn]["in_progress"] += 1
        elif item.status == "At Risk":
            sections[sn]["at_risk"] += 1

    directorates: dict = {}
    for item in items:
        d = item.directorate
        if d not in directorates:
            directorates[d] = {"directorate": d, "total": 0, "completed": 0, "in_progress": 0}
        directorates[d]["total"] += 1
        if item.status == "Completed":
            directorates[d]["completed"] += 1
        elif item.status == "In Progress":
            directorates[d]["in_progress"] += 1

    return {
        "total": total,
        "completed": completed,
        "in_progress": in_progress,
        "at_risk": at_risk,
        "not_started": total - completed - in_progress - at_risk,
        "sections": sorted(sections.values(), key=lambda x: x["section_number"]),
        "directorates": sorted(directorates.values(), key=lambda x: x["directorate"]),
    }


@router.get("/export")
async def export_checklist(
    directorate: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(ChecklistItem).order_by(ChecklistItem.section_number, ChecklistItem.item_order)
    staff_directorate = _staff_directorate_filter(user)
    if staff_directorate is not None:
        stmt = stmt.where(ChecklistItem.directorate == staff_directorate)
    elif directorate:
        stmt = stmt.where(ChecklistItem.directorate == directorate)
    result = await db.execute(stmt)
    items = result.scalars().all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Master Checklist"

    headers = [
        "Section", "Section Title", "Subsection", "Directorate", "Item",
        "Status", "Progress %", "Notes", "Updated By", "Updated At",
    ]
    ws.append(headers)

    for i in items:
        ws.append([
            i.section_number, i.section_title, i.subsection, i.directorate, i.item_text,
            i.status, i.progress_pct, i.notes, i.updated_by,
            i.updated_at.isoformat() if i.updated_at else "",
        ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    effective_directorate = staff_directorate or directorate
    filename = f"CLET_Master_Checklist{'_' + effective_directorate if effective_directorate else ''}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/comments/recent", response_model=list[RecentChecklistCommentOut])
async def get_recent_checklist_comments(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = (
        select(
            ChecklistComment.id,
            ChecklistComment.author_name,
            ChecklistComment.content,
            ChecklistComment.created_at,
            ChecklistItem.id.label("item_id"),
            ChecklistItem.item_text,
            ChecklistItem.section_number,
            ChecklistItem.section_title,
            ChecklistItem.directorate,
        )
        .join(ChecklistItem, ChecklistComment.item_id == ChecklistItem.id)
        .order_by(ChecklistComment.created_at.desc())
        .limit(20)
    )
    rows = (await db.execute(stmt)).all()
    return [
        RecentChecklistCommentOut(
            id=row.id,
            author_name=row.author_name,
            content=row.content,
            created_at=row.created_at,
            item_id=row.item_id,
            item_text=row.item_text,
            section_number=row.section_number,
            section_title=row.section_title,
            directorate=row.directorate,
        )
        for row in rows
    ]


@router.get("/{item_id}/comments", response_model=list[ChecklistCommentOut])
async def list_checklist_comments(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChecklistComment)
        .where(ChecklistComment.item_id == item_id)
        .order_by(ChecklistComment.created_at)
    )
    return result.scalars().all()


@router.post("/{item_id}/comments", response_model=ChecklistCommentOut)
async def add_checklist_comment(
    item_id: str,
    body: ChecklistCommentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = (await db.execute(select(ChecklistItem).where(ChecklistItem.id == item_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    _assert_can_touch_item(user, item)

    comment = ChecklistComment(
        id=str(uuid.uuid4()),
        item_id=item_id,
        author_name=body.author_name or user.name,
        content=body.content,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    await manager.broadcast({
        "type": "CHECKLIST_COMMENT_ADDED",
        "payload": {"item_id": item_id, "section_number": item.section_number},
    })

    return comment


@router.patch("/{item_id}", response_model=ChecklistItemOut)
async def update_checklist_item(
    item_id: str,
    body: ChecklistItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(ChecklistItem).where(ChecklistItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    _assert_can_touch_item(user, item)

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(item, field, value)

    if not body.updated_by:
        item.updated_by = user.name

    await db.commit()
    await db.refresh(item)

    await manager.broadcast({"type": "CHECKLIST_UPDATED", "payload": {"id": item.id}})

    return item
