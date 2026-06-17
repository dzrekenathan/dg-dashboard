from pydantic import BaseModel, EmailStr
from typing import Optional


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str
    email: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str

    model_config = {"from_attributes": True}


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
