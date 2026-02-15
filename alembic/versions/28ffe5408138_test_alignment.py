from alembic import op
import sqlalchemy as sa

revision ="28ffe5408138"
down_revision = "1d4e6f876f20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # If businesses table doesn't exist, skip safely
    if not conn.execute(sa.text("SELECT to_regclass('core.businesses')")).scalar():
        return

    # Drop FK if exists
    fk_exists = conn.execute(sa.text("""
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname='core'
          AND t.relname='businesses'
          AND c.conname='businesses_business_type_id_fkey'
        LIMIT 1
    """)).scalar()

    if fk_exists:
        op.drop_constraint(
            "businesses_business_type_id_fkey",
            "businesses",
            schema="core",
            type_="foreignkey",
        )

    # Drop index if exists
    idx_exists = conn.execute(sa.text("""
        SELECT 1
        FROM pg_indexes
        WHERE schemaname='core'
          AND tablename='businesses'
          AND indexname='idx_businesses_business_type_id'
        LIMIT 1
    """)).scalar()

    if idx_exists:
        op.drop_index(
            "idx_businesses_business_type_id",
            table_name="businesses",
            schema="core",
        )

    # Drop column if exists
    col_exists = conn.execute(sa.text("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema='core'
          AND table_name='businesses'
          AND column_name='business_type_id'
        LIMIT 1
    """)).scalar()

    if col_exists:
        op.drop_column("businesses", "business_type_id", schema="core")

    # Drop table if exists
    if conn.execute(sa.text("SELECT to_regclass('core.business_types')")).scalar():
        op.drop_table("business_types", schema="core")

def downgrade() -> None:
    op.create_table(
        "business_types",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by_admin_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="core",
    )

    op.add_column(
        "businesses",
        sa.Column("business_type_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        schema="core",
    )

    op.create_index(
        "idx_businesses_business_type_id",
        "businesses",
        ["business_type_id"],
        schema="core",
    )

    op.create_foreign_key(
        "businesses_business_type_id_fkey",
        "businesses",
        "business_types",
        ["business_type_id"],
        ["id"],
        source_schema="core",
        referent_schema="core",
    )
