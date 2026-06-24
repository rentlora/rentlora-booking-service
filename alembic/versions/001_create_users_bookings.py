"""create users and bookings

Revision ID: 001_create_users_bookings
Revises:
Create Date: 2026-05-25
"""

import sqlalchemy as sa
from alembic import op

revision = "001_create_users_bookings"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), server_default="guest"),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()")),
        sa.CheckConstraint("role IN ('guest','host','admin')", name="users_role_check"),
    )
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("guest_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("check_in", sa.Date(), nullable=False),
        sa.Column("check_out", sa.Date(), nullable=False),
        sa.Column("guests_count", sa.Integer(), nullable=False),
        sa.Column("total_nights", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="confirmed"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()")),
        sa.CheckConstraint("status IN ('confirmed','cancelled','completed')", name="bookings_status_check"),
    )


def downgrade() -> None:
    op.drop_table("bookings")
    op.drop_table("users")
