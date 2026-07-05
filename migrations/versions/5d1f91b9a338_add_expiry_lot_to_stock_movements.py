"""add expiry_date and lot_number to stock_movements

Revision ID: 5d1f91b9a338
Revises: 2002c9b32491
Create Date: 2026-07-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '5d1f91b9a338'
down_revision: Union[str, Sequence[str], None] = '2002c9b32491'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # El proveedor a veces indica fecha de caducidad y número de lote en el
    # albarán (Textract + Claude ya los extraen en AlbaranLine), pero hasta
    # ahora se descartaban silenciosamente al no existir columna donde
    # guardarlos. Sin esto no se puede construir la alerta de caducidad de
    # Fase 3. Ambas columnas nullable porque no todos los albaranes las traen.
    op.add_column('stock_movements', sa.Column('expiry_date', sa.Date(), nullable=True))
    op.add_column('stock_movements', sa.Column('lot_number', sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('stock_movements', 'lot_number')
    op.drop_column('stock_movements', 'expiry_date')