"""SQLAlchemy engine + session factory, shared by the app and by scripts/migrations."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Session:
    """Yield-style session for FastAPI dependency injection, once the API layer exists."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
