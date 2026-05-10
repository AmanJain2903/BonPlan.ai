"""Add is_public to trips

Revision ID: c3d9f12a4e87
Revises: b565e513b7d4
Create Date: 2026-05-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d9f12a4e87'
down_revision: Union[str, Sequence[str], None] = 'b565e513b7d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trips', sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('trips', 'is_public')
