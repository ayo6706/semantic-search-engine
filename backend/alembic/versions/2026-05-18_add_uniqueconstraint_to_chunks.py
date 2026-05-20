"""Add UniqueConstraint to chunks

Revision ID: 2878117469c7
Revises: 39aed91c9191
Create Date: 2026-05-18 14:20:48.978244

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2878117469c7'
down_revision: Union[str, Sequence[str], None] = '39aed91c9191'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint('uq_chunk_doc_id_index', 'chunks', ['doc_id', 'chunk_index'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_chunk_doc_id_index', 'chunks', type_='unique')
