from alembic import op
import sqlalchemy as sa

revision ="28ffe5408138"
down_revision = "1d4e6f876f20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1️⃣ Drop FK
    op.drop_constraint(
        "businesses_business_type_id_fkey",
        "businesses",
        schema="core",
        type_="foreignkey",
    )

    # 2️⃣ Drop index
    op.drop_index(
        "idx_businesses_business_type_id",
        table_name="businesses",
        schema="core",
    )

    # 3️⃣ Drop column
    op.drop_column("businesses", "business_type_id", schema="core")

    # 4️⃣ Drop table
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
