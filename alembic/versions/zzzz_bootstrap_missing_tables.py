from alembic import op

# IMPORTANT: make this unique
revision = "zzzz_bootstrap_missing_tables"

# IMPORTANT: this must be your current latest revision from logs:
down_revision = "4af691f1a46f"

branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS core;")
    # DO NOT create_all here. Keep bootstrap empty.
    pass

def downgrade() -> None:
    # no-op (we don't want to drop tables automatically)
    pass
