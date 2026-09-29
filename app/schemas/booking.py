"""Booking request/response schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import BookingStatus


class BookingCreate(BaseModel):
    centre_id: uuid.UUID
    test_id: uuid.UUID
    appointment_at: datetime


class BookingResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    centre_id: uuid.UUID
    test_id: uuid.UUID
    amount: Decimal
    status: BookingStatus
    appointment_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
