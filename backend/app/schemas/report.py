"""Pydantic schemas for workout analysis report responses."""

from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict


class JobReportResponse(BaseModel):
    """Aggregated workout summary report schema for a specific job."""

    job_id: uuid.UUID
    total_reps: int
    average_rom: Optional[float] = None
    average_tempo: Optional[float] = None
    average_score: Optional[float] = None
    summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
