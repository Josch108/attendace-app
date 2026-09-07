#!/usr/bin/env python3
"""
Database initialization script.
Creates all tables defined in SQLAlchemy models.
Works with both local SQLite and PostgreSQL based on DATABASE_URL.
"""
import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import engine
from app.db.base import Base
# Import all models so that Base.metadata registers them
import app.models  # noqa: F401
from app.config import settings

def init_database():
    print("=== Initializing Database ===")
    print(f"Connection URL: {settings.DATABASE_URL}")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    tables = list(Base.metadata.tables.keys())
    print(f"Successfully created tables ({len(tables)}):")
    for table in sorted(tables):
        print(f"  - {table}")
    print("=============================")

if __name__ == "__main__":
    init_database()
