"""enable_draft_business_flow

Revision ID: 4af691f1a46f
Revises: f06d9f66995e
Create Date: 2026-02-14 17:07:04.906411

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4af691f1a46f'
down_revision: Union[str, Sequence[str], None] = 'f06d9f66995e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Allow timezone nullable
    op.execute("ALTER TABLE core.businesses ALTER COLUMN timezone DROP NOT NULL")

    # Allow business_name nullable
    op.execute("ALTER TABLE core.businesses ALTER COLUMN business_name DROP NOT NULL")

    # Change default status to DRAFT
    op.execute("ALTER TABLE core.businesses ALTER COLUMN status SET DEFAULT 'DRAFT'")

    # Drop FK constraint first
    op.execute("ALTER TABLE core.businesses DROP CONSTRAINT IF EXISTS businesses_business_type_id_fkey")

    # Drop index
    op.execute("DROP INDEX IF EXISTS core.idx_businesses_business_type_id")

    # Drop column
    op.execute("ALTER TABLE core.businesses DROP COLUMN IF EXISTS business_type_id")

    # Drop industry column
    op.execute("ALTER TABLE core.businesses DROP COLUMN IF EXISTS industry")

    # Drop enum type
    op.execute("DROP TYPE IF EXISTS core.industry_enum")

    # Add service_type_name column
    op.execute("ALTER TABLE core.businesses ADD COLUMN IF NOT EXISTS service_type_name VARCHAR(120)")



def downgrade() -> None:
    """Downgrade schema."""
    pass
