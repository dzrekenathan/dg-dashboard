"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("so_number", sa.String(10), index=True, nullable=False),
        sa.Column("so_title", sa.String(500), default=""),
        sa.Column("thematic_area", sa.String(255), default=""),
        sa.Column("task", sa.Text(), default=""),
        sa.Column("reference_numbers", sa.Text(), default=""),
        sa.Column("activities", sa.Text(), default=""),
        sa.Column("timeframe", sa.String(255), default=""),
        sa.Column("responsibility", sa.String(255), default=""),
        sa.Column("outputs", sa.Text(), default=""),
        sa.Column("outcomes", sa.Text(), default=""),
        sa.Column("risks_mitigation", sa.Text(), default=""),
        sa.Column("budget", sa.String(255), default=""),
        sa.Column("status", sa.String(50), default="Not Started"),
        sa.Column("progress_pct", sa.Integer(), default=0),
        sa.Column("assigned_to", sa.String(255), default=""),
        sa.Column("target_date", sa.String(50), default=""),
        sa.Column("notes", sa.Text(), default=""),
        sa.Column("last_updated", sa.String(50), default=""),
        sa.Column("updated_by", sa.String(255), default=""),
    )
    op.create_table(
        "so_visibility",
        sa.Column("so_number", sa.String(10), primary_key=True),
        sa.Column("is_visible", sa.Boolean(), default=True, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("so_visibility")
    op.drop_table("tasks")
    op.drop_table("users")
