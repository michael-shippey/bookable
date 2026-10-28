from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# The engine manages the pool of connections to Postgres.
# pool_pre_ping checks a connection is alive before using it.
engine = create_engine(settings.database_url, pool_pre_ping=True)

# A session is one "conversation" with the database (one unit of work).
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """All of our models will inherit from this class."""


def get_db():
    """FastAPI dependency: gives each request its own session, then closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
