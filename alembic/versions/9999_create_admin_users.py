from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "9999_create_admin_users"
down_revision = "4af691f1a46f"  # from your log: enable_draft_business_flow
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS core;")
    op.execute("""
    CREATE TABLE IF NOT EXISTS core.admin_users (
        id UUID PRIMARY KEY,
        email VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        full_name VARCHAR(255),
        role VARCHAR(50) NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT true,
        last_login_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    );
    """)


def downgrade() -> None:
    op.drop_table("admin_users", schema="core")
