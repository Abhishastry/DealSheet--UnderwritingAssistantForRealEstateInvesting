"""SQLAlchemy engine + session factory, shared by the app and by scripts/migrations."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    future=True,
    # Long-running scripts (e.g. run_qualification.py over hundreds of
    # properties, mostly spent waiting on the Anthropic API between DB calls)
    # let pooled connections sit idle long enough for Supabase's session
    # pooler to recycle them server-side. Without pre_ping, SQLAlchemy hands
    # out that now-dead connection and the next query fails with "server
    # closed the connection unexpectedly" instead of transparently
    # reconnecting. pool_recycle proactively retires connections before they
    # get old enough to hit that server-side timeout in the first place.
    pool_pre_ping=True,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Session:
    """Yield-style session for FastAPI dependency injection, once the API layer exists."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
