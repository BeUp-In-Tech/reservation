from sqlalchemy import create_engine, text

# ⚠️ PUT YOUR REAL PASSWORD HERE
url = "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/reservation_dev"

engine = create_engine(url)

with engine.connect() as conn:
    print("DB ID:",
          conn.execute(
              text("select current_database(), current_user, inet_server_addr(), inet_server_port()")
          ).first()
    )

    print("search_path:",
          conn.execute(text("show search_path")).scalar()
    )

    print("to_regclass(core.alembic_version):",
          conn.execute(text("select to_regclass('core.alembic_version')")).scalar()
    )

    print("version rows:",
          conn.execute(text("select * from core.alembic_version")).all()
    )
