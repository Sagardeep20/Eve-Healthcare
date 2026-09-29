"""Import all models so Alembic autogenerate and Base.metadata see every table."""

from app.models.booking import Booking  # noqa: F401
from app.models.centre import DiagnosticCentre  # noqa: F401
from app.models.centre_test import CentreTest  # noqa: F401
from app.models.enums import BookingStatus, PaymentStatus  # noqa: F401
from app.models.payment import Payment  # noqa: F401
from app.models.test import DiagnosticTest  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.webhook_event import WebhookEvent  # noqa: F401
