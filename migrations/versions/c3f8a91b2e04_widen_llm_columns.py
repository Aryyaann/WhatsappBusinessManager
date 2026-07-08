"""widen llm_intent and llm_tool_called columns

Revision ID: c3f8a91b2e04
Revises: 8a1f3c5e9d21
Create Date: 2026-07-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3f8a91b2e04'
down_revision: Union[str, Sequence[str], None] = '8a1f3c5e9d21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'conversation_messages', 'llm_intent',
        type_=sa.String(255),
        existing_type=sa.String(100),
    )
    op.alter_column(
        'conversation_messages', 'llm_tool_called',
        type_=sa.String(255),
        existing_type=sa.String(100),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'conversation_messages', 'llm_tool_called',
        type_=sa.String(100),
        existing_type=sa.String(255),
    )
    op.alter_column(
        'conversation_messages', 'llm_intent',
        type_=sa.String(100),
        existing_type=sa.String(255),
    )