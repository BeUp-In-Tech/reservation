"""init

Revision ID: a367c14926a1
Revises: 
Create Date: 2026-02-03 10:19:39.073865

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a367c14926a1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # ✅ Ensure schema exists
    op.execute("CREATE SCHEMA IF NOT EXISTS core;")

    # ✅ Create all tables from SQLAlchemy models (in core schema)
    from app.core.database import Base
    Base.metadata.create_all(bind=op.get_bind())

def downgrade() -> None:
    from app.core.database import Base
    Base.metadata.drop_all(bind=op.get_bind())

    # optional:
    # op.execute("DROP SCHEMA IF EXISTS core CASCADE;")