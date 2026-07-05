"""add pgvector extension and hnsw index on products.embedding

Revision ID: 2002c9b32491
Revises: eef3e4ce40bf
Create Date: 2026-07-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2002c9b32491'
down_revision: Union[str, Sequence[str], None] = 'eef3e4ce40bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # La extensión ya tenía que estar activa a mano en RDS/local para que la
    # migración inicial pudiera crear products.embedding como VECTOR(1536),
    # pero nunca quedó versionada. La dejamos aquí de forma idempotente para
    # que cualquier entorno nuevo (otro dev, staging, CI) la tenga sin pasos
    # manuales fuera de Alembic.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Índice HNSW para búsqueda por similitud coseno sobre products.embedding.
    # Se usa HNSW en vez de ivfflat porque no requiere el parámetro 'lists'
    # (que depende del volumen de filas) y da buen recall incluso con la
    # tabla vacía o con pocos productos, que es nuestro caso ahora mismo en
    # fase de desarrollo. m=16 / ef_construction=64 son los valores por
    # defecto recomendados por pgvector para este caso de uso.
    op.create_index(
        "ix_products_embedding_hnsw",
        "products",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_products_embedding_hnsw", table_name="products")
    # No hacemos DROP EXTENSION vector: es una operación a nivel de servidor
    # y otras tablas podrían depender de ella. Si hace falta quitarla del
    # todo, se hace a mano y de forma consciente, no en un downgrade automático.