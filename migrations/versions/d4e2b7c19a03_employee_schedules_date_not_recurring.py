"""employee_schedules: day_of_week -> date (deja de ser recurrente)

Revision ID: d4e2b7c19a03
Revises: c3f8a91b2e04
Create Date: 2026-07-09 00:00:00.000000

IMPORTANTE: esta migración BORRA los horarios existentes en
employee_schedules. El concepto cambia de "se repite todas las semanas
igual" a "turno de una fecha concreta", y no hay forma automática de
convertir uno en el otro — el horario recurrente que hubiera se pierde y
hay que volver a planificarlo semana a semana desde el panel.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e2b7c19a03'
down_revision: Union[str, Sequence[str], None] = 'c3f8a91b2e04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DELETE FROM employee_schedules")
    op.add_column('employee_schedules', sa.Column('date', sa.Date(), nullable=True))
    op.execute("UPDATE employee_schedules SET date = CURRENT_DATE")  # no debería quedar ninguna fila tras el DELETE, es solo por seguridad
    op.alter_column('employee_schedules', 'date', nullable=False)
    op.drop_column('employee_schedules', 'day_of_week')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('employee_schedules', sa.Column('day_of_week', sa.Integer(), nullable=True))
    op.execute("DELETE FROM employee_schedules")
    op.alter_column('employee_schedules', 'day_of_week', nullable=False)
    op.drop_column('employee_schedules', 'date')
