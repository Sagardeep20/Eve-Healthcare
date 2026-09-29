"""Booking routes (all require authentication)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingResponse
from app.services import booking_service
from app.services.booking_service import BookingError

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail="Booking not found")


@router.post("", response_model=BookingResponse, status_code=201)
def create_booking(
    payload: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return booking_service.create_booking(
            db, current_user, payload.centre_id, payload.test_id, payload.appointment_at
        )
    except BookingError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("", response_model=list[BookingResponse])
def list_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return booking_service.list_for_user(db, current_user)


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return booking_service.get_owned_booking(db, current_user, _parse_uuid(booking_id))
    except BookingError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return booking_service.cancel_booking(db, current_user, _parse_uuid(booking_id))
    except BookingError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
