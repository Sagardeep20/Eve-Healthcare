"""WebhookEvent model for idempotent webhook processing."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, JSON, String, func, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Unique provider-supplied event id for idempotency (enforced at DB level).
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
