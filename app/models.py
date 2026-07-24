import enum
from datetime import datetime, timezone, date
from sqlalchemy import String, Integer, Boolean, DateTime, Date, Text, Enum, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from sqlalchemy.dialects.postgresql import UUID
import uuid


class UserRole(str, enum.Enum):
    STAFF = "staff"
    DG = "dg"
    REGISTRAR = "registrar"
    SUPER_ADMIN = "super_admin"


class Directorate(str, enum.Enum):
    GSL = "GSL"
    CDT = "CDT"
    AQAI = "AQAI"
    LRKS = "LRKS"
    DTI = "DTI"
    CCP = "CCP"
    PTC = "PTC"
    FRM = "FRM"
    SFL = "SFL"
    CA = "CA"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    directorate: Mapped[Directorate | None] = mapped_column(
        Enum(Directorate, native_enum=False, length=10, values_callable=lambda e: [m.value for m in e]),
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    so_number: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    so_title: Mapped[str] = mapped_column(String(500), default="")
    thematic_area: Mapped[str] = mapped_column(String(255), default="")
    task: Mapped[str] = mapped_column(Text, default="")
    reference_numbers: Mapped[str] = mapped_column(Text, default="")
    activities: Mapped[str] = mapped_column(Text, default="")
    timeframe: Mapped[str] = mapped_column(String(255), default="")
    responsibility: Mapped[str] = mapped_column(String(255), default="")
    outputs: Mapped[str] = mapped_column(Text, default="")
    outcomes: Mapped[str] = mapped_column(Text, default="")
    risks_mitigation: Mapped[str] = mapped_column(Text, default="")
    budget: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(50), default="Not Started")
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    assigned_to: Mapped[str] = mapped_column(String(255), default="")
    target_date: Mapped[str] = mapped_column(String(50), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    last_updated: Mapped[str] = mapped_column(String(50), default="")
    updated_by: Mapped[str] = mapped_column(String(255), default="")


class ActivityTracking(Base):
    __tablename__ = "activity_tracking"
    __table_args__ = (UniqueConstraint("task_id", "activity_ref", name="uq_task_activity"),)

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    activity_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="Not Started")
    assigned_to: Mapped[str] = mapped_column(String(255), default="")
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    target_date: Mapped[str] = mapped_column(String(50), default="")


class ActivityComment(Base):
    __tablename__ = "activity_comments"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    tracking_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    author_name: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SOVisibility(Base):
    __tablename__ = "so_visibility"

    so_number: Mapped[str] = mapped_column(String(10), primary_key=True)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SystemProgress(Base):
    __tablename__ = "system_progress"

    system_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="Not Started")
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PhaseDeadline(Base):
    __tablename__ = "phase_deadlines"

    phase: Mapped[int] = mapped_column(Integer, primary_key=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FlexAdmin(Base):
    """Emails on this list are asked to choose their access (a directorate, DG or
    Registrar) every time they sign in, instead of keeping a fixed role."""
    __tablename__ = "flex_admins"

    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    added_by: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SupportRequest(Base):
    __tablename__ = "support_requests"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    requester_email: Mapped[str] = mapped_column(String(255), nullable=False)
    requester_name: Mapped[str] = mapped_column(String(255), default="")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="New")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
