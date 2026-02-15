from app.core.database import Base
import app.models

print("=== MODELS REGISTERED ===")
for table in Base.metadata.tables:
    print(table)
