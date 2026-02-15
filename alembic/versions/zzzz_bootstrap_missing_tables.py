from alembic import op

# IMPORTANT: make this unique
revision = "zzzz_bootstrap_missing_tables"

# IMPORTANT: this must be your current latest revision from logs:
down_revision = "4af691f1a46f"

branch_labels = None
depends_on = None


def upgrade() -> None:
    # make sure schema exists
    op.execute("CREATE SCHEMA IF NOT EXISTS core;")
    op.execute("SET search_path TO core, public;")

    # load all models so metadata is complete
    import app.models  # noqa: F401
    from app.core.database import Base

    # create any missing tables (won't drop existing)
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # no-op (we don't want to drop tables automatically)
    pass
