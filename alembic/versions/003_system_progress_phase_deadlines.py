"""system progress and phase deadlines

Revision ID: 003
Revises: 002
Create Date: 2026-07-22
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_progress",
        sa.Column("system_code", sa.String(length=20), primary_key=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="Not Started"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "phase_deadlines",
        sa.Column("phase", sa.Integer(), primary_key=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("phase_deadlines")
    op.drop_table("system_progress")
