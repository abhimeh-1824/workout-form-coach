from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    """Public user identity response schema."""

    id: uuid.UUID
    provider: str
    provider_user_id: str
    email: str
    name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
