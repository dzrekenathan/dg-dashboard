"""google sso

Revision ID: 002
Revises: 001
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_users_google_id", "users", ["google_id"])
    op.execute("UPDATE users SET role = 'staff' WHERE role = 'management'")
    op.drop_column("users", "password_hash")


def downgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.execute("UPDATE users SET role = 'management' WHERE role = 'staff'")
    op.drop_constraint("uq_users_google_id", "users", type_="unique")
    op.drop_column("users", "google_id")
