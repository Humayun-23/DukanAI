import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# Database URL - PostgreSQL
# Set DATABASE_URL environment variable or it will use default
# Example: postgresql://username:password@localhost:5432/rentwheels
if all([settings.pguser, settings.pgpassword, settings.pghost, settings.pgport, settings.pgdatabase]):
    DATABASE_URL = f"postgresql://{settings.pguser}:{settings.pgpassword}@{settings.pghost}:{settings.pgport}/{settings.pgdatabase}?sslmode={settings.pgsslmode}&channel_binding={settings.pgchannelbinding}"
else:
    DATABASE_URL = settings.database_url

if not DATABASE_URL:
    raise ValueError("Database configuration is missing. Please set either DATABASE_URL or individual PostgreSQL environment variables.")

engine = create_engine(
    DATABASE_URL,
    pool_size=20,           # Max persistent connections
    max_overflow=0,         # No additional connections beyond pool_size
    pool_pre_ping=True,     # Verify connections before use
    pool_recycle=3600,      # Recycle connections after 1 hour
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()