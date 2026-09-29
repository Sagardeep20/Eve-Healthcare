"""Diagnostic test response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class TestResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
