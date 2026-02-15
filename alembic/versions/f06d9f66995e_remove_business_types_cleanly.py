"""remove business_types cleanly

Revision ID: f06d9f66995e
Revises: 28ffe5408138
Create Date: 2026-02-14 15:26:41.111537

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f06d9f66995e"
down_revision: Union[str, Sequence[str], None] = '28ffe5408138'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
