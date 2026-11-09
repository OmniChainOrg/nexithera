"""
SQLAlchemy ORM session management for CogPM provisioning and spend tracking.

This module provides SQLAlchemy SessionLocal and get_db() dependency
for FastAPI endpoints that need ORM access (provisioning, spend enforcement).

The main app uses asyncpg (core/database.py) for most operations.
This is specifically for CogPM tables (installations, deployments, usage events, alerts).
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# Create SQLAlchemy engine for CogPM tables
# Uses same database as main app but accesses via ORM
engine = create_engine(
    f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}",
    pool_pre_ping=True,  # Test connection before using
    pool_size=10,
    max_overflow=20,
    echo=False,  # Set to True for SQL debugging
)

# Event listener to ensure foreign key constraints are enabled
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """For PostgreSQL, ensure foreign keys and constraints are enforced."""
    # PostgreSQL enforces these by default, but this pattern is compatible
    pass

# SessionLocal factory for creating sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Dependency injection for FastAPI endpoints.
    Provides SQLAlchemy Session for database access.
    
    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    
    Yields:
        SQLAlchemy Session
    
    Ensures:
        - Session is committed on success
        - Session is rolled back on error
        - Session is always closed
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
