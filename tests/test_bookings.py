"""Booking API tests: creation, retrieval, cancellation, authorization."""

import uuid

from tests.helpers import APPOINTMENT, create_booking


def test_create_booking_success(client, user_a, ids):
    centres, tests = ids
    res = create_booking(client, user_a, centres, tests)
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "PENDING"
    assert float(body["amount"]) == 500.00  # from centre_tests, not client input
    assert body["appointment_at"].startswith("2026-10-02T10:00:00")
    assert body["user_id"]


def test_create_booking_amount_snapshot(client, user_a, ids, db_session):
    """Price snapshot: old booking keeps 500, a new booking uses the new 600."""
    from decimal import Decimal

    from sqlalchemy import select

    from app.models.centre_test import CentreTest

    centres, tests = ids
    old = create_booking(client, user_a, centres, tests).json()
    assert float(old["amount"]) == 500.00

    centre_id = uuid.UUID(centres["Apollo Diagnostics"])
    test_id = uuid.UUID(tests["CBC"])
    ct = db_session.scalar(
        select(CentreTest).where(
            CentreTest.centre_id == centre_id, CentreTest.test_id == test_id
        )
    )
    ct.price = Decimal("600.00")
    db_session.commit()

    got_old = client.get(f"/api/bookings/{old['id']}", headers=user_a)
    assert float(got_old.json()["amount"]) == 500.00

    new = create_booking(client, user_a, centres, tests).json()
    assert float(new["amount"]) == 600.00


def test_create_booking_invalid_centre(client, user_a, ids):
    _, tests = ids
    res = client.post(
        "/api/bookings",
        headers=user_a,
        json={"centre_id": str(uuid.uuid4()), "test_id": tests["CBC"],
              "appointment_at": APPOINTMENT},
    )
    assert res.status_code == 404


def test_create_booking_invalid_test(client, user_a, ids):
    centres, _ = ids
    res = client.post(
        "/api/bookings",
        headers=user_a,
        json={"centre_id": centres["Apollo Diagnostics"], "test_id": str(uuid.uuid4()),
              "appointment_at": APPOINTMENT},
    )
    assert res.status_code == 404


def test_create_booking_test_not_offered_by_centre(client, user_a, ids):
    # Dr Lal PathLabs does not offer Thyroid Profile in seed data.
    centres, tests = ids
    res = create_booking(client, user_a, centres, tests,
                         centre="Dr Lal PathLabs", test="Thyroid Profile")
    assert res.status_code == 400


def test_create_booking_malformed_datetime(client, user_a, ids):
    centres, tests = ids
    res = client.post(
        "/api/bookings",
        headers=user_a,
        json={"centre_id": centres["Apollo Diagnostics"], "test_id": tests["CBC"],
              "appointment_at": "not-a-datetime"},
    )
    assert res.status_code == 422


def test_create_booking_missing_fields(client, user_a, ids):
    centres, _ = ids
    res = client.post(
        "/api/bookings", headers=user_a,
        json={"centre_id": centres["Apollo Diagnostics"]},
    )
    assert res.status_code == 422


def test_create_booking_unauthenticated(client, ids):
    centres, tests = ids
    res = client.post(
        "/api/bookings",
        json={"centre_id": centres["Apollo Diagnostics"], "test_id": tests["CBC"],
              "appointment_at": APPOINTMENT},
    )
    assert res.status_code == 401


def test_list_bookings_only_own(client, user_a, user_b, ids):
    centres, tests = ids
    create_booking(client, user_a, centres, tests)
    create_booking(client, user_b, centres, tests)
    res = client.get("/api/bookings", headers=user_a)
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_get_own_booking(client, user_a, ids):
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    res = client.get(f"/api/bookings/{booking_id}", headers=user_a)
    assert res.status_code == 200
    assert res.json()["id"] == booking_id


def test_cannot_access_another_users_booking(client, user_a, user_b, ids):
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    res = client.get(f"/api/bookings/{booking_id}", headers=user_b)
    assert res.status_code == 404


def test_get_booking_invalid_id(client, user_a):
    assert client.get("/api/bookings/not-a-uuid", headers=user_a).status_code == 404
    assert client.get(f"/api/bookings/{uuid.uuid4()}", headers=user_a).status_code == 404


def test_cancel_pending_booking(client, user_a, ids):
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    res = client.post(f"/api/bookings/{booking_id}/cancel", headers=user_a)
    assert res.status_code == 200
    assert res.json()["status"] == "CANCELLED"


def test_cancel_confirmed_booking(client, user_a, ids):
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    pay = client.post("/api/payments/", headers=user_a,
                      json={"booking_id": booking_id, "simulate_status": "SUCCESS"})
    assert pay.status_code == 201
    res = client.post(f"/api/bookings/{booking_id}/cancel", headers=user_a)
    assert res.status_code == 200
    assert res.json()["status"] == "CANCELLED"


def test_cancel_already_cancelled_booking(client, user_a, ids):
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    assert client.post(f"/api/bookings/{booking_id}/cancel", headers=user_a).status_code == 200
    res = client.post(f"/api/bookings/{booking_id}/cancel", headers=user_a)
    assert res.status_code == 409


def test_cancel_failed_booking_rejected(client, user_a, ids):
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    pay = client.post("/api/payments/", headers=user_a,
                      json={"booking_id": booking_id, "simulate_status": "FAILED"})
    assert pay.status_code == 201
    res = client.post(f"/api/bookings/{booking_id}/cancel", headers=user_a)
    assert res.status_code == 409


def test_cannot_cancel_another_users_booking(client, user_a, user_b, ids):
    centres, tests = ids
    booking_id = create_booking(client, user_a, centres, tests).json()["id"]
    res = client.post(f"/api/bookings/{booking_id}/cancel", headers=user_b)
    assert res.status_code == 404
    # Owner's booking untouched.
    assert client.get(f"/api/bookings/{booking_id}", headers=user_a).json()["status"] == "PENDING"
