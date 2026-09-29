"""Webhook tests: processing, idempotent replays, conflicts, validation."""

import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
import app.models  # noqa: F401 - register all tables on fresh metadata users
from app.models.booking import Booking
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.enums import BookingStatus, PaymentStatus
from app.models.payment import Payment
from app.models.test import DiagnosticTest
from app.models.user import User
from app.models.webhook_event import WebhookEvent
from app.services.payment_service import process_webhook
from tests.helpers import create_booking


def _pay(client, headers, booking_id, status):
    return client.post(
        "/api/payments/",
        headers=headers,
        json={"booking_id": booking_id, "simulate_status": status},
    )


def _webhook(client, event_id, payment_id, status):
    return client.post(
        "/api/payments/webhook",
        json={"event_id": event_id, "payment_id": payment_id, "status": status},
    )


def _counts(db_session):
    return (
        db_session.scalar(select(func.count()).select_from(Booking)),
        db_session.scalar(select(func.count()).select_from(Payment)),
        db_session.scalar(select(func.count()).select_from(WebhookEvent)),
    )


def test_webhook_success_upgrades_failed_payment(client, user_a, ids, db_session):
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    provider_ref = _pay(client, user_a, booking_id, "FAILED").json()["provider_ref"]

    res = _webhook(client, "evt_001", provider_ref, "SUCCESS")
    assert res.status_code == 200
    assert res.json()["processed"] is True

    payment = db_session.scalar(select(Payment).where(Payment.provider_ref == provider_ref))
    booking = db_session.get(Booking, uuid.UUID(booking_id))
    assert payment.status.value == "SUCCESS"
    assert booking.status.value == "CONFIRMED"


def test_webhook_failed_after_success_is_ignored(client, user_a, ids, db_session):
    """SUCCESS is terminal: a conflicting FAILED event is recorded, state kept."""
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    provider_ref = _pay(client, user_a, booking_id, "SUCCESS").json()["provider_ref"]

    res = _webhook(client, "evt_conflict_1", provider_ref, "FAILED")
    assert res.status_code == 200
    assert res.json()["processed"] is False

    booking = db_session.get(Booking, uuid.UUID(booking_id))
    assert booking.status.value == "CONFIRMED"


def test_webhook_unknown_payment(client):
    res = _webhook(client, "evt_nope", "pay_does_not_exist", "SUCCESS")
    assert res.status_code == 404


def test_webhook_invalid_payload(client):
    assert client.post("/api/payments/webhook", json={}).status_code == 422
    res = client.post(
        "/api/payments/webhook",
        json={"event_id": "e1", "payment_id": "p1", "status": "PENDING"},
    )
    assert res.status_code == 422


def test_webhook_on_cancelled_booking_keeps_cancelled(client, user_a, ids, db_session):
    """Regression: a webhook must never resurrect a CANCELLED booking."""
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    provider_ref = _pay(client, user_a, booking_id, "SUCCESS").json()["provider_ref"]
    assert client.post(f"/api/bookings/{booking_id}/cancel", headers=user_a).status_code == 200

    res = _webhook(client, "evt_cancelled_1", provider_ref, "SUCCESS")
    assert res.status_code == 200
    assert res.json()["processed"] is False

    booking = db_session.get(Booking, uuid.UUID(booking_id))
    payment = db_session.scalar(select(Payment).where(Payment.provider_ref == provider_ref))
    assert booking.status.value == "CANCELLED"
    assert payment.status.value == "SUCCESS"

    # Replay is ignored and adds no further rows.
    replay = _webhook(client, "evt_cancelled_1", provider_ref, "SUCCESS")
    assert replay.json()["processed"] is False
    assert _counts(db_session) == (1, 1, 1)


def test_webhook_duplicate_event_idempotent(client, user_a, ids, db_session):
    """Same event 3x: one event row, one payment, one booking, correct state."""
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    provider_ref = _pay(client, user_a, booking_id, "FAILED").json()["provider_ref"]

    first = _webhook(client, "evt_001", provider_ref, "SUCCESS")
    assert first.status_code == 200
    assert first.json()["processed"] is True

    second = _webhook(client, "evt_001", provider_ref, "SUCCESS")
    third = _webhook(client, "evt_001", provider_ref, "SUCCESS")
    assert second.json()["processed"] is False
    assert third.json()["processed"] is False

    n_bookings, n_payments, n_events = _counts(db_session)
    # Fixture seeds no bookings/payments/events, so exactly one of each.
    assert (n_bookings, n_payments, n_events) == (1, 1, 1)

    booking = db_session.get(Booking, uuid.UUID(booking_id))
    assert booking.status.value == "CONFIRMED"


def test_webhook_replay_does_not_create_duplicates(client, user_a, ids, db_session):
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    provider_ref = _pay(client, user_a, booking_id, "SUCCESS").json()["provider_ref"]

    before = _counts(db_session)
    results = [_webhook(client, "evt_replay_same", provider_ref, "SUCCESS") for _ in range(3)]
    assert [r.status_code for r in results] == [200, 200, 200]
    assert [r.json()["processed"] for r in results] == [True, False, False]
    # First delivery processed; replays added no rows.
    assert _counts(db_session) == (before[0], before[1], before[2] + 1)

    booking = db_session.get(Booking, uuid.UUID(booking_id))
    assert booking.status.value == "CONFIRMED"


def test_concurrent_duplicate_webhooks_single_effect(tmp_path):
    """Two threads racing the same event: one processes, one is ignored."""
    db_file = tmp_path / "race.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"timeout": 30})
    try:
        Base.metadata.create_all(engine)
        Maker = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        setup = Maker()
        user = User(name="Racy", email="racy@example.com", hashed_password="x")
        centre = DiagnosticCentre(name="C", location="L")
        test = DiagnosticTest(name="T")
        setup.add_all([user, centre, test])
        setup.flush()
        setup.add(CentreTest(centre_id=centre.id, test_id=test.id, price=Decimal("500.00")))
        setup.flush()
        booking = Booking(
            user_id=user.id, centre_id=centre.id, test_id=test.id,
            amount=Decimal("500.00"),
            appointment_at=datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc),
            status=BookingStatus.PENDING,
        )
        setup.add(booking)
        setup.flush()
        payment = Payment(
            booking_id=booking.id, amount=Decimal("500.00"),
            status=PaymentStatus.FAILED, provider_ref="pay_race_1",
        )
        setup.add(payment)
        setup.commit()
        booking_id, ref = booking.id, payment.provider_ref
        setup.close()

        barrier = threading.Barrier(2)
        results = []

        def worker():
            db = Maker()
            try:
                barrier.wait(timeout=30)
                results.append(process_webhook(db, "evt_race", ref, PaymentStatus.SUCCESS))
            finally:
                db.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        assert all(not t.is_alive() for t in threads)
        assert sorted(r[0] for r in results) == [False, True]

        check = Maker()
        try:
            assert check.scalar(select(func.count()).select_from(WebhookEvent)) == 1
            assert check.scalar(select(func.count()).select_from(Payment)) == 1
            assert check.get(Booking, booking_id).status == BookingStatus.CONFIRMED
        finally:
            check.close()
    finally:
        engine.dispose()
