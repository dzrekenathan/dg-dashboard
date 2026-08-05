"""checklist target_date and comments

Revision ID: 005
Revises: 004
Create Date: 2026-08-04
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "checklist_items",
        sa.Column("target_date", sa.String(length=50), nullable=False, server_default=""),
    )
    op.create_table(
        "checklist_comments",
        sa.Column("id", sa.String(length=50), primary_key=True),
        sa.Column("item_id", sa.String(length=50), nullable=False),
        sa.Column("author_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_checklist_comments_item_id", "checklist_comments", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_checklist_comments_item_id", table_name="checklist_comments")
    op.drop_table("checklist_comments")
    op.drop_column("checklist_items", "target_date")
