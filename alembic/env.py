from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from sqlalchemy.orm import declarative_base
Base = declarative_base()

# Ensure all model classes are imported so metadata is complete
import app.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url(url: str) -> str:
    """Convert any postgres URL to sync psycopg2 format for Alembic."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    return url


def run_migrations_offline() -> None:
    url = _sync_url(settings.DATABASE_URL)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table="alembic_version",
        version_table_schema="core",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _sync_url(settings.DATABASE_URL)

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # ✅ Ensure schema exists before migrations
        connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS core;")
        connection.exec_driver_sql("SET search_path TO core, public;")

        # ===== DIAGNOSTIC ONLY (optional) =====
        print("=== ALEMBIC DB DEBUG ===")
        row = connection.exec_driver_sql(
            """
            SELECT current_database(), current_user,
                   inet_server_addr()::text, inet_server_port()::text,
                   current_setting('search_path');
            """
        ).first()
        print("ALEMBIC CONNECTED TO:", row)

        reg = connection.exec_driver_sql(
            "SELECT to_regclass('core.alembic_version')"
        ).scalar()
        print("to_regclass(core.alembic_version) =", reg)
        print("=== END ALEMBIC DB DEBUG ===")
        # =====================================

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table="alembic_version",
            version_table_schema="core",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
