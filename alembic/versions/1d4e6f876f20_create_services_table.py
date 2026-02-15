"""create services table

Revision ID: 1d4e6f876f20
Revises: a367c14926a1
Create Date: 2026-02-14 10:55:59.543902

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d4e6f876f20'
down_revision: Union[str, Sequence[str], None] = 'a367c14926a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
