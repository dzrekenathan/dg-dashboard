from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import SOVisibility, User
from app.schemas import SOVisibilityMap
from app.core.security import get_current_user, require_management
from app.core.ws_manager import manager

router = APIRouter(prefix="/so-visibility", tags=["so-visibility"])

SOS = ["SO1", "SO2", "SO3", "SO4"]


async def _ensure_rows(db: AsyncSession):
    """Seed missing visibility rows with default True."""
    result = await db.execute(select(SOVisibility))
    existing = {row.so_number for row in result.scalars().all()}
    for so in SOS:
        if so not in existing:
            db.add(SOVisibility(so_number=so, is_visible=True))
    await db.commit()


@router.get("", response_model=SOVisibilityMap)
async def get_visibility(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    await _ensure_rows(db)
    result = await db.execute(select(SOVisibility))
    rows = {r.so_number: r.is_visible for r in result.scalars().all()}
    return SOVisibilityMap(
        SO1=rows.get("SO1", True),
        SO2=rows.get("SO2", True),
        SO3=rows.get("SO3", True),
        SO4=rows.get("SO4", True),
    )


@router.patch("/{so_number}", response_model=SOVisibilityMap)
async def toggle_visibility(
    so_number: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_management),
):
    await _ensure_rows(db)
    result = await db.execute(select(SOVisibility).where(SOVisibility.so_number == so_number))
    row = result.scalar_one_or_none()
    if row:
        row.is_visible = not row.is_visible
        await db.commit()

    # Return the full map so the frontend can sync in one call
    all_rows_result = await db.execute(select(SOVisibility))
    rows = {r.so_number: r.is_visible for r in all_rows_result.scalars().all()}
    visibility = SOVisibilityMap(
        SO1=rows.get("SO1", True),
        SO2=rows.get("SO2", True),
        SO3=rows.get("SO3", True),
        SO4=rows.get("SO4", True),
    )

    await manager.broadcast({"type": "VISIBILITY_UPDATED", "payload": visibility.model_dump()})
    return visibility
