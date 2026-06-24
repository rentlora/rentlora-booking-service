"""Add platform fee

Revision ID: 002_add_platform_fee
Revises: 001_create_users_bookings
Create Date: 2026-06-17 12:55:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '002_add_platform_fee'
down_revision: Union[str, None] = '001_create_users_bookings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Set default platform fee to 0.00 for existing bookings
    op.add_column('bookings', sa.Column('platform_fee', sa.Numeric(precision=10, scale=2), server_default='0.00', nullable=False))


def downgrade() -> None:
    op.drop_column('bookings', 'platform_fee')
