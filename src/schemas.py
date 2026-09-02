import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    info: dict
    sample_count: int
    created_at: datetime
    updated_at: datetime


class IdentifyResponse(BaseModel):
    person: PersonResponse
    similarity: float
    sample_added: bool = False
    closest_sample_similarity: float | None = None


class FaceSampleResponse(BaseModel):
    person: PersonResponse
    sample_added: bool
    closest_sample_similarity: float | None = None
