import inspect
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine, get_db


def test_database_url_configuration() -> None:
    """Verify DATABASE_URL is configured and uses postgresql+psycopg scheme."""
    assert settings.DATABASE_URL is not None
    assert settings.DATABASE_URL.startswith("postgresql+psycopg://")


def test_declarative_base_setup() -> None:
    """Verify Base inherits from DeclarativeBase and has valid metadata."""
    assert issubclass(Base, DeclarativeBase)
    assert hasattr(Base, "metadata")


def test_engine_configuration() -> None:
    """Verify SQLAlchemy engine is configured with matching URL and driver."""
    assert engine.url.drivername == "postgresql+psycopg"


def test_get_db_generator() -> None:
    """Verify get_db is a generator function for FastAPI dependency injection."""
    assert inspect.isgeneratorfunction(get_db)
