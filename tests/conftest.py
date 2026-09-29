"""Pytest fixtures: SQLite-backed app with overridden DB dependency."""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    session = TestingSession()

    # Minimal catalogue shared by centre/test tests.
    centre_a = DiagnosticCentre(id=uuid.uuid4(), name="Apollo Diagnostics", location="Bangalore")
    centre_b = DiagnosticCentre(id=uuid.uuid4(), name="Dr Lal PathLabs", location="Delhi")
    test_cbc = DiagnosticTest(id=uuid.uuid4(), name="CBC", description="Complete Blood Count")
    test_thyroid = DiagnosticTest(id=uuid.uuid4(), name="Thyroid Profile", description="T3, T4, TSH")
    session.add_all([centre_a, centre_b, test_cbc, test_thyroid])
    session.flush()
    session.add_all(
        [
            CentreTest(centre_id=centre_a.id, test_id=test_cbc.id, price=Decimal("500.00")),
            CentreTest(centre_id=centre_a.id, test_id=test_thyroid.id, price=Decimal("900.00")),
            CentreTest(centre_id=centre_b.id, test_id=test_cbc.id, price=Decimal("450.00")),
        ]
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    """Sign up + log in a user, return Authorization headers."""
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    client.post(
        "/api/auth/signup",
        json={"name": "Test User", "email": email, "password": "password123"},
    )
    login = client.post(
        "/api/auth/login", json={"email": email, "password": "password123"}
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_a(client):
    from tests.helpers import make_user_headers

    headers, _ = make_user_headers(client, "User A")
    return headers


@pytest.fixture()
def user_b(client):
    from tests.helpers import make_user_headers

    headers, _ = make_user_headers(client, "User B")
    return headers


@pytest.fixture()
def ids(db_session):
    from tests.helpers import catalogue_ids

    return catalogue_ids(db_session)
