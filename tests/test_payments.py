"""Simulated payment tests: state transitions, amounts, conflicts, authz."""

import uuid

from tests.helpers import create_booking


def _pay(client, headers, booking_id, status):
    return client.post(
        "/api/payments/",
        headers=headers,
        json={"booking_id": booking_id, "simulate_status": status},
    )


def test_successful_payment_confirms_booking(client, user_a, ids):
    centres, tests = ids
    booking = create_booking(client, user_a, centres, tests).json()
    res = _pay(client, user_a, booking["id"], "SUCCESS")
    assert res.status_code == 201
    payment = res.json()
    assert payment["status"] == "SUCCESS"
    assert float(payment["amount"]) == float(booking["amount"])  # amount from booking
    assert payment["provider_ref"]

    got = client.get(f"/api/bookings/{booking['id']}", headers=user_a)
    assert got.json()["status"] == "CONFIRMED"


def test_failed_payment_marks_booking_failed(client, user_a, ids):
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    res = _pay(client, user_a, booking_id, "FAILED")
    assert res.status_code == 201
    assert res.json()["status"] == "FAILED"
    got = client.get(f"/api/bookings/{booking_id}", headers=user_a)
    assert got.json()["status"] == "FAILED"


def test_payment_nonexistent_booking(client, user_a):
    assert _pay(client, user_a, str(uuid.uuid4()), "SUCCESS").status_code == 404


def test_payment_unauthenticated(client, user_a, ids):
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    res = client.post(
        "/api/payments/",
        json={"booking_id": booking_id, "simulate_status": "SUCCESS"},
    )
    assert res.status_code == 401


def test_cannot_pay_for_another_users_booking(client, user_a, user_b, ids):
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    res = _pay(client, user_b, booking_id, "SUCCESS")
    assert res.status_code == 404


def test_duplicate_payment_rejected(client, user_a, ids, db_session):
    from sqlalchemy import func, select

    from app.models.payment import Payment

    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    assert _pay(client, user_a, booking_id, "SUCCESS").status_code == 201
    res = _pay(client, user_a, booking_id, "SUCCESS")
    assert res.status_code == 409
    assert db_session.scalar(select(func.count()).select_from(Payment)) == 1


def test_payment_on_cancelled_booking_rejected(client, user_a, ids):
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    assert client.post(f"/api/bookings/{booking_id}/cancel", headers=user_a).status_code == 200
    assert _pay(client, user_a, booking_id, "SUCCESS").status_code == 409


def test_payment_on_failed_booking_rejected(client, user_a, ids, db_session):
    """A failed booking cannot become confirmed through another payment."""
    from sqlalchemy import func, select

    from app.models.payment import Payment

    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    assert _pay(client, user_a, booking_id, "FAILED").status_code == 201
    assert _pay(client, user_a, booking_id, "SUCCESS").status_code == 409
    n_payments = db_session.scalar(select(func.count()).select_from(Payment))
    assert n_payments == 1
    got = client.get(f"/api/bookings/{booking_id}", headers=user_a)
    assert got.json()["status"] == "FAILED"


def test_payment_invalid_status(client, user_a, ids):
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    res = client.post(
        "/api/payments/",
        headers=user_a,
        json={"booking_id": booking_id, "simulate_status": "PENDING"},
    )
    assert res.status_code == 422
