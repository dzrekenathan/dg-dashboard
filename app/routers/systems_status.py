import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import SystemProgress, PhaseDeadline, User, UserRole
from app.schemas import SystemProgressOut, SystemProgressUpdate, PhaseDeadlineOut, PhaseDeadlineUpdate
from app.core.security import get_current_user, require_role
from app.core.ws_manager import manager
from app.systems_catalog import get_system_directorate, list_all_systems

router = APIRouter(prefix="/systems", tags=["systems-status"])


@router.get("/status", response_model=list[SystemProgressOut])
async def list_system_status(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(SystemProgress))
    return result.scalars().all()


@router.get("/export")
async def export_systems_status(
    directorate: Optional[str] = Query(None, description="If set, only include systems owned by this directorate"),
    codes: Optional[str] = Query(None, description="If set, only include these comma-separated system codes"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(SystemProgress))
    status_by_code = {row.system_code: row for row in result.scalars().all()}

    systems = list_all_systems()
    if directorate:
        systems = [s for s in systems if s["directorate"] == directorate]
    if codes:
        wanted = {c.strip() for c in codes.split(",") if c.strip()}
        systems = [s for s in systems if s["code"] in wanted]

    wb = Workbook()
    ws = wb.active
    ws.title = "Systems Status"

    headers = [
        "Code", "System Name", "Phase", "Directorate", "Status",
        "Progress %", "Last Updated", "Updated By",
    ]
    ws.append(headers)

    for sys in systems:
        row = status_by_code.get(sys["code"])
        ws.append([
            sys["code"], sys["name"], sys["phase"], sys["directorate"],
            row.status if row else "Not Started",
            row.progress_pct if row else 0,
            row.updated_at.isoformat() if row and row.updated_at else "",
            row.updated_by if row else "",
        ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"CLET_Systems_Status{'_' + directorate if directorate else ''}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/status/{code}", response_model=SystemProgressOut)
async def update_system_status(
    code: str,
    body: SystemProgressUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == UserRole.STAFF:
        system_directorate = get_system_directorate(code)
        if system_directorate is None or user.directorate is None or system_directorate != user.directorate.value:
            raise HTTPException(status_code=403, detail="You can only update systems in your own directorate")
    elif user.role not in (UserRole.DG, UserRole.REGISTRAR, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="You do not have access to update system status")

    result = await db.execute(select(SystemProgress).where(SystemProgress.system_code == code))
    row = result.scalar_one_or_none()
    if row is None:
        row = SystemProgress(system_code=code)
        db.add(row)

    if body.status is not None:
        row.status = body.status
    if body.progress_pct is not None:
        row.progress_pct = body.progress_pct
    row.updated_by = user.email

    await db.commit()
    await db.refresh(row)

    out = SystemProgressOut.model_validate(row)
    await manager.broadcast({"type": "SYSTEM_STATUS_UPDATED", "payload": out.model_dump(mode="json")})
    return out


@router.get("/deadlines", response_model=list[PhaseDeadlineOut])
async def list_phase_deadlines(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(PhaseDeadline))
    return result.scalars().all()


@router.patch("/deadlines/{phase}", response_model=PhaseDeadlineOut)
async def update_phase_deadline(
    phase: int,
    body: PhaseDeadlineUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.DG, UserRole.REGISTRAR, UserRole.SUPER_ADMIN)),
):
    result = await db.execute(select(PhaseDeadline).where(PhaseDeadline.phase == phase))
    row = result.scalar_one_or_none()
    if row is None:
        row = PhaseDeadline(phase=phase)
        db.add(row)

    row.deadline = body.deadline
    row.updated_by = user.email

    await db.commit()
    await db.refresh(row)

    out = PhaseDeadlineOut.model_validate(row)
    await manager.broadcast({"type": "PHASE_DEADLINE_UPDATED", "payload": out.model_dump(mode="json")})
    return out
