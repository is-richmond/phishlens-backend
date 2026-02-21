"""
PhishLens Database Configuration

Provides SQLAlchemy engine, session factory, and base model class.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://phishlens_user:phishlens_dev_password@localhost:5432/phishlens_db",
)

_engine_kwargs: dict = {
    "echo": os.getenv("DEBUG", "false").lower() == "true",
}

if SQLALCHEMY_DATABASE_URL.startswith("postgresql"):
    _engine_kwargs.update(pool_size=10, max_overflow=20, pool_pre_ping=True)
elif SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    _engine_kwargs.update(
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

engine = create_engine(SQLALCHEMY_DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
