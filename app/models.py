from datetime import datetime, timezone
from sqlalchemy import String, Integer, Boolean, DateTime, Text, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # 'dg' | 'management'
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
