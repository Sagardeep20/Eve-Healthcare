"""Simulated payment + webhook business logic."""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.enums import BookingStatus, PaymentStatus
from app.models.payment import Payment
from app.models.user import User
from app.models.webhook_event import WebhookEvent


class PaymentError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _apply_payment_result(booking: Booking, payment: Payment, status: PaymentStatus) -> None:
    """Set payment + booking states consistently (single transaction by caller)."""
    if status == PaymentStatus.SUCCESS:
        payment.status = PaymentStatus.SUCCESS
        booking.status = BookingStatus.CONFIRMED
    else:
        payment.status = PaymentStatus.FAILED
        booking.status = BookingStatus.FAILED


def create_payment(
    db: Session, user: User, booking_id: uuid.UUID, simulate_status: PaymentStatus
) -> Payment:
    booking = db.get(Booking, booking_id)
    # 404 for missing OR not-owned bookings: never leak other users' bookings.
    if booking is None or booking.user_id != user.id:
        raise PaymentError(404, "Booking not found")
    if booking.status == BookingStatus.CANCELLED:
        raise PaymentError(409, "Cannot pay for a cancelled booking")
    if booking.status == BookingStatus.CONFIRMED:
        raise PaymentError(409, "Booking has already been paid")
    if booking.status != BookingStatus.PENDING:
        raise PaymentError(409, f"Booking in status {booking.status.value} cannot be paid")
    existing = db.scalar(select(Payment).where(Payment.booking_id == booking.id))
    if existing is not None:
        raise PaymentError(409, "Payment already exists for this booking")

    payment = Payment(
        booking_id=booking.id,
        amount=booking.amount,  # amount from DB, never from the client
        status=simulate_status,  # provisional; set together with booking below
        provider_ref=f"pay_{uuid.uuid4().hex}",
    )
    # Create payment + update booking atomically so they can never diverge
    # (e.g. payment=SUCCESS with booking still PENDING).
    _apply_payment_result(booking, payment, simulate_status)
    try:
        db.add(payment)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(payment)
    return payment


def _record_event(db: Session, event_id: str, payment_id: str, status: PaymentStatus) -> bool:
    """Insert the webhook event row. Returns False if it was already recorded.

    The unique constraint on webhook_events.event_id is the idempotency
    backstop: concurrent duplicate deliveries raise IntegrityError here and
    are treated as duplicates. The rollback only discards this request's own
    uncommitted changes; the winning delivery already committed the state.
    """
    try:
        db.add(
            WebhookEvent(
                event_id=event_id,
                payload={"payment_id": payment_id, "status": status.value},
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True


def process_webhook(
    db: Session, event_id: str, payment_id: str, status: PaymentStatus
) -> tuple[bool, str]:
    """Process a provider webhook idempotently.

    Returns (processed, detail). Duplicate event_ids are ignored without
    any state change. Assumptions (documented, kept simple):
    - SUCCESS is a terminal payment state: a later *new* FAILED event is
      recorded but does not downgrade an already-successful payment/booking,
      protecting against stale/conflicting replays.
    - CANCELLED is a terminal booking state: webhooks never move a cancelled
      booking back to CONFIRMED/FAILED; the event is recorded and ignored.
    """
    already = db.scalar(select(WebhookEvent).where(WebhookEvent.event_id == event_id))
    if already is not None:
        return False, "Duplicate event ignored"

    payment = db.scalar(select(Payment).where(Payment.provider_ref == payment_id))
    if payment is None:
        raise PaymentError(404, "Payment not found")
    booking = db.get(Booking, payment.booking_id)
    if booking is None:  # defensive; FK should prevent this
        raise PaymentError(404, "Booking not found")

    if booking.status == BookingStatus.CANCELLED:
        # Cancelled bookings stay cancelled: record the event, change nothing.
        if not _record_event(db, event_id, payment_id, status):
            return False, "Duplicate event ignored"
        return False, "Event ignored; booking is CANCELLED"

    if payment.status == PaymentStatus.SUCCESS and status == PaymentStatus.FAILED:
        # Terminal-state guard: record the event, keep the success.
        if not _record_event(db, event_id, payment_id, status):
            return False, "Duplicate event ignored"
        return False, "Conflicting event ignored; payment already SUCCESS"

    _apply_payment_result(booking, payment, status)
    if not _record_event(db, event_id, payment_id, status):
        # Lost a race with a concurrent identical event: treat as duplicate.
        return False, "Duplicate event ignored"
    return True, "Event processed"
