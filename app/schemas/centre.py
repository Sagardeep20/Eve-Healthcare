"""Centre response schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CentreResponse(BaseModel):
    id: uuid.UUID
    name: str
    location: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CentreTestItem(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    price: Decimal

    model_config = {"from_attributes": True}


class CentreDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    location: str
    tests: list[CentreTestItem] = []

    model_config = {"from_attributes": True}
