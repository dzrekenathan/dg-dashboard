from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db
from app.models import FlexAdmin, SupportRequest, User
from app.schemas import (
    FlexAdminOut, FlexAdminCreate,
    SupportRequestOut, SupportRequestCreate, SupportRequestStatusUpdate,
)
from app.core.security import get_current_user, require_super_admin_email
from app.admin_accounts import is_super_admin_email

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Flexible-access accounts (super admin only) ─────────────────────────────────

@router.get("/flex-admins", response_model=list[FlexAdminOut])
async def list_flex_admins(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_super_admin_email),
):
    result = await db.execute(select(FlexAdmin).order_by(FlexAdmin.created_at))
    return result.scalars().all()


@router.post("/flex-admins", response_model=FlexAdminOut)
async def add_flex_admin(
    body: FlexAdminCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_super_admin_email),
):
    email = body.email.lower().strip()
    if not email.endswith("@gslaw.edu.gh"):
        raise HTTPException(status_code=400, detail="Enter a valid @gslaw.edu.gh email address")
    if is_super_admin_email(email):
        raise HTTPException(status_code=400, detail="The super admin account cannot be a flexible-access account")

    existing = (await db.execute(select(FlexAdmin).where(FlexAdmin.email == email))).scalar_one_or_none()
    if existing:
        return existing

    flex = FlexAdmin(email=email, added_by=user.email)
    db.add(flex)
    await db.commit()
    await db.refresh(flex)
    return flex


@router.delete("/flex-admins/{email}", status_code=204)
async def remove_flex_admin(
    email: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_super_admin_email),
):
    await db.execute(delete(FlexAdmin).where(FlexAdmin.email == email.lower().strip()))
    await db.commit()


# ── Support / change requests ───────────────────────────────────────────────────

@router.post("/support-requests", response_model=SupportRequestOut)
async def create_support_request(
    body: SupportRequestCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    req = SupportRequest(
        requester_email=user.email,
        requester_name=user.name,
        message=body.message.strip(),
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return req


@router.get("/support-requests", response_model=list[SupportRequestOut])
async def list_support_requests(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_super_admin_email),
):
    result = await db.execute(select(SupportRequest).order_by(SupportRequest.created_at.desc()))
    return result.scalars().all()


@router.patch("/support-requests/{request_id}", response_model=SupportRequestOut)
async def update_support_request_status(
    request_id: str,
    body: SupportRequestStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_super_admin_email),
):
    result = await db.execute(select(SupportRequest).where(SupportRequest.id == request_id))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if body.status not in ("New", "Reviewed", "Resolved"):
        raise HTTPException(status_code=400, detail="Invalid status")
    req.status = body.status
    await db.commit()
    await db.refresh(req)
    return req
