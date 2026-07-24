from datetime import date, datetime
from pydantic import BaseModel
from typing import Optional
from app.models import UserRole, Directorate


# ── Auth ──────────────────────────────────────────────────────────────────────

class ExchangeRequest(BaseModel):
    code: str


class OnboardingCompleteRequest(BaseModel):
    onboarding_token: str
    directorate: Directorate


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    name: str
    email: str
    directorate: Directorate | None = None


class OnboardingRequiredResponse(BaseModel):
    needs_onboarding: bool = True
    onboarding_token: str


class RoleSelectionRequiredResponse(BaseModel):
    needs_role_selection: bool = True
    role_select_token: str


class RoleSelectionCompleteRequest(BaseModel):
    role_select_token: str
    role: UserRole
    directorate: Optional[Directorate] = None


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: UserRole
    directorate: Directorate | None = None

    model_config = {"from_attributes": True}


# ── Flex admins & support requests ──────────────────────────────────────────────

class FlexAdminOut(BaseModel):
    email: str
    added_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FlexAdminCreate(BaseModel):
    email: str


class SupportRequestCreate(BaseModel):
    message: str


class SupportRequestOut(BaseModel):
    id: str
    requester_email: str
    requester_name: str
    message: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SupportRequestStatusUpdate(BaseModel):
    status: str

# ── Tasks ─────────────────────────────────────────────────────────────────────

class TaskOut(BaseModel):
    id: str
    so_number: str
    so_title: str
    thematic_area: str
    task: str
    reference_numbers: str
    activities: str
    timeframe: str
    responsibility: str
    outputs: str
    outcomes: str
    risks_mitigation: str
    budget: str
    status: str
    progress_pct: int
    assigned_to: str
    target_date: str
    notes: str
    last_updated: str
    updated_by: str

    model_config = {"from_attributes": True}


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    progress_pct: Optional[int] = None
    assigned_to: Optional[str] = None
    target_date: Optional[str] = None
    notes: Optional[str] = None
    updated_by: Optional[str] = None
    last_updated: Optional[str] = None


class TaskBulkImport(BaseModel):
    tasks: list[TaskOut]


# ── SO Visibility ─────────────────────────────────────────────────────────────

class SOVisibilityOut(BaseModel):
    so_number: str
    is_visible: bool

    model_config = {"from_attributes": True}


class SOVisibilityMap(BaseModel):
    SO1: bool
    SO2: bool
    SO3: bool
    SO4: bool


# ── Activity Tracking ─────────────────────────────────────────────────────────

class ActivityCommentOut(BaseModel):
    id: str
    author_name: str
    content: str
    created_at: str

    model_config = {"from_attributes": True}


class ActivityTrackingOut(BaseModel):
    id: str
    task_id: str
    activity_ref: str
    status: str
    assigned_to: str
    progress_pct: int = 0
    target_date: str = ""
    comments: list[ActivityCommentOut] = []

    model_config = {"from_attributes": True}


class ActivityTrackingUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    progress_pct: Optional[int] = None
    target_date: Optional[str] = None


class ActivityCommentCreate(BaseModel):
    content: str
    author_name: str = ""


class RecentCommentOut(BaseModel):
    id: str
    author_name: str
    content: str
    created_at: str
    task_id: str
    activity_ref: str
    so_number: str
    thematic_area: str
    task_name: str


# ── WebSocket messages ────────────────────────────────────────────────────────

class WSMessage(BaseModel):
    type: str          # 'TASKS_UPDATED' | 'VISIBILITY_UPDATED' | 'PING'
    payload: dict = {}


# ── Systems Status & Phase Deadlines ──────────────────────────────────────────

class SystemProgressOut(BaseModel):
    system_code: str
    status: str
    progress_pct: int
    updated_by: str | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class SystemProgressUpdate(BaseModel):
    status: Optional[str] = None
    progress_pct: Optional[int] = None


class PhaseDeadlineOut(BaseModel):
    phase: int
    deadline: date | None = None
    updated_by: str | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class PhaseDeadlineUpdate(BaseModel):
    deadline: date
