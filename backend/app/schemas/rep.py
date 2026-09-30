"""Pydantic schemas for repetition analysis responses."""

from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class FormIssueResponse(BaseModel):
    """Schema for individual form issues detected during repetition analysis."""

    code: str
    message: str
    severity: str = "warning"

    model_config = ConfigDict(from_attributes=True)


class RepItemResponse(BaseModel):
    """Repetition metrics and form analysis response schema."""

    rep_number: int
    start_time: float
    end_time: float
    rom: Optional[float] = None
    tempo: Optional[float] = None
    form_score: Optional[float] = None
    issues: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class JobRepsResponse(BaseModel):
    """Collection of completed repetitions for a specific job."""

    job_id: uuid.UUID
    total_reps: int
    reps: List[RepItemResponse]

    model_config = ConfigDict(from_attributes=True)
