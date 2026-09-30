from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy database models."""
    pass


# Register all models with Base.metadata so Alembic and SQLAlchemy discover them
from app.models.user import User  # noqa: E402
from app.models.job import ExerciseType, Job, JobStatus, SourceType  # noqa: E402
from app.models.rep import Rep  # noqa: E402
from app.models.report import Report  # noqa: E402

__all__ = [
    "Base",
    "User",
    "Job",
    "JobStatus",
    "ExerciseType",
    "SourceType",
    "Rep",
    "Report",
]
