"""add service_id to appointments

Revision ID: 8a1f3c5e9d21
Revises: 0cb49d880843
Create Date: 2026-07-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8a1f3c5e9d21'
down_revision: Union[str, Sequence[str], None] = '0cb49d880843'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'appointments',
        sa.Column('service_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_appointments_service_id',
        'appointments',
        'services',
        ['service_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_appointments_service_id', 'appointments', type_='foreignkey')
    op.drop_column('appointments', 'service_id')