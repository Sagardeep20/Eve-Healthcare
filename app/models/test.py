"""DiagnosticTest model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DiagnosticTest(Base):
    __tablename__ = "diagnostic_tests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    centre_tests: Mapped[list["CentreTest"]] = relationship(
        back_populates="test", cascade="all, delete-orphan"
    )
