from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.core.database import Base

# Ensure all model classes are imported so metadata is complete
import app.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url(async_url: str) -> str:
    """
    Alembic migrations run in sync mode here (psycopg),
    while the app may use asyncpg. Convert async URL -> sync URL.
    """
    if async_url.startswith("postgresql+asyncpg://"):
        return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return async_url


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
        # ===== DIAGNOSTIC ONLY (no behavior change) =====
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

        tables = connection.exec_driver_sql(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_name='alembic_version';
            """
        ).all()
        print("alembic_version tables:", tables)
        print("=== END ALEMBIC DB DEBUG ===")
        # ==============================================

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
