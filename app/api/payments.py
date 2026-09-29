"""Simulated payment + provider webhook routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.payment import (
    PaymentCreate,
    PaymentResponse,
    WebhookRequest,
    WebhookResponse,
)
from app.services import payment_service
from app.services.payment_service import PaymentError

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("/", response_model=PaymentResponse, status_code=201)
def create_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return payment_service.create_payment(
            db, current_user, payload.booking_id, payload.simulate_status
        )
    except PaymentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/webhook", response_model=WebhookResponse)
def payment_webhook(payload: WebhookRequest, db: Session = Depends(get_db)):
    """Simulated external provider callback. No user auth (provider-to-server)."""
    try:
        processed, detail = payment_service.process_webhook(
            db, payload.event_id, payload.payment_id, payload.status
        )
    except PaymentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return WebhookResponse(
        event_id=payload.event_id, processed=processed, detail=detail
    )
