"""Payment + webhook request/response schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import PaymentStatus


class PaymentCreate(BaseModel):
    booking_id: uuid.UUID
    simulate_status: PaymentStatus


class PaymentResponse(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    amount: Decimal
    status: PaymentStatus
    provider_ref: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=255)
    payment_id: str = Field(min_length=1, max_length=255)
    status: PaymentStatus


class WebhookResponse(BaseModel):
    event_id: str
    processed: bool
    detail: str
