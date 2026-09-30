import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.job import Job


class User(Base):
    """User model representing authenticated users."""

    __tablename__ = "users"

    __table_args__ = (
        sa.UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_users_provider_provider_user_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    provider: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
    )
    provider_user_id: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        sa.String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[Optional[str]] = mapped_column(
        sa.String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    jobs: Mapped[List["Job"]] = relationship(
        "Job",
        back_populates="user",
        cascade="all, delete-orphan",
    )
