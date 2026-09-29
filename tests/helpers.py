"""Shared helpers for phase-2 (booking/payment/webhook) tests."""

import uuid

from sqlalchemy import select

from app.models.centre import DiagnosticCentre
from app.models.test import DiagnosticTest


def make_user_headers(client, name="Test User"):
    """Sign up + log in a fresh user; return (headers, email)."""
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    res = client.post(
        "/api/auth/signup",
        json={"name": name, "email": email, "password": "password123"},
    )
    assert res.status_code == 201
    login = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, email


def catalogue_ids(db_session):
    """Return {centre_name: id, test_name: id} for the seeded catalogue."""
    centres = {c.name: str(c.id) for c in db_session.scalars(select(DiagnosticCentre)).all()}
    tests = {t.name: str(t.id) for t in db_session.scalars(select(DiagnosticTest)).all()}
    return centres, tests


APPOINTMENT = "2026-10-02T10:00:00"


def create_booking(client, headers, centres, tests, centre="Apollo Diagnostics",
                   test="CBC", appointment=APPOINTMENT):
    return client.post(
        "/api/bookings",
        headers=headers,
        json={"centre_id": centres[centre], "test_id": tests[test],
              "appointment_at": appointment},
    )
