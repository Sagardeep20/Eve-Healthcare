"""Booking business logic (state transitions live here, not in routers)."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.enums import BookingStatus
from app.models.test import DiagnosticTest
from app.models.user import User


class BookingError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# Bookings in these states may be cancelled.
_CANCELLABLE = {BookingStatus.PENDING, BookingStatus.CONFIRMED}


def create_booking(
    db: Session,
    user: User,
    centre_id: uuid.UUID,
    test_id: uuid.UUID,
    appointment_at: datetime,
) -> Booking:
    centre = db.get(DiagnosticCentre, centre_id)
    if centre is None:
        raise BookingError(404, "Centre not found")
    test = db.get(DiagnosticTest, test_id)
    if test is None:
        raise BookingError(404, "Test not found")
    centre_test = db.scalar(
        select(CentreTest).where(
            CentreTest.centre_id == centre_id,
            CentreTest.test_id == test_id,
        )
    )
    if centre_test is None:
        raise BookingError(400, "Test is not offered by the selected centre")

    # Amount always comes from the DB price snapshot, never from the client.
    booking = Booking(
        user_id=user.id,
        centre_id=centre_id,
        test_id=test_id,
        amount=centre_test.price,
        appointment_at=appointment_at,
        status=BookingStatus.PENDING,
    )
    try:
        db.add(booking)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(booking)
    return booking


def list_for_user(db: Session, user: User) -> list[Booking]:
    return list(
        db.scalars(
            select(Booking)
            .where(Booking.user_id == user.id)
            .order_by(Booking.created_at.desc())
        ).all()
    )


def get_owned_booking(db: Session, user: User, booking_id: uuid.UUID) -> Booking:
    """Return the booking only if owned by the user; 404 otherwise.

    Returning 404 (instead of 403) for another user's booking avoids
    leaking the existence of bookings to unauthorized users.
    """
    booking = db.get(Booking, booking_id)
    if booking is None or booking.user_id != user.id:
        raise BookingError(404, "Booking not found")
    return booking


def cancel_booking(db: Session, user: User, booking_id: uuid.UUID) -> Booking:
    booking = get_owned_booking(db, user, booking_id)
    if booking.status not in _CANCELLABLE:
        raise BookingError(
            409, f"Booking in status {booking.status.value} cannot be cancelled"
        )
    booking.status = BookingStatus.CANCELLED
    db.commit()
    db.refresh(booking)
    return booking
