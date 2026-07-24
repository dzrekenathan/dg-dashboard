"""flex admins and support requests

Revision ID: 004
Revises: 003
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flex_admins",
        sa.Column("email", sa.String(length=255), primary_key=True),
        sa.Column("added_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "support_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("requester_email", sa.String(length=255), nullable=False),
        sa.Column("requester_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="New"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("support_requests")
    op.drop_table("flex_admins")
