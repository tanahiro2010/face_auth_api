import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    info: dict
    created_at: datetime
    updated_at: datetime


class IdentifyResponse(BaseModel):
    person: PersonResponse
    similarity: float
