"""Auth tests: signup, login, and the get_current_user dependency."""

import uuid


def _email():
    return f"user-{uuid.uuid4().hex[:8]}@example.com"


def test_signup_success(client):
    res = client.post(
        "/api/auth/signup",
        json={"name": "Alice", "email": _email(), "password": "password123"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == body["email"].lower()
    assert "hashed_password" not in body
    assert "password" not in body
    assert "id" in body


def test_signup_duplicate_email(client):
    email = _email()
    payload = {"name": "Bob", "email": email, "password": "password123"}
    assert client.post("/api/auth/signup", json=payload).status_code == 201
    # Case-insensitive duplicate must also be rejected.
    dup = client.post(
        "/api/auth/signup",
        json={"name": "Bob 2", "email": email.upper(), "password": "password123"},
    )
    assert dup.status_code == 409


def test_signup_validation(client):
    # Missing password.
    res = client.post("/api/auth/signup", json={"name": "X", "email": _email()})
    assert res.status_code == 422
    # Malformed email.
    res = client.post(
        "/api/auth/signup",
        json={"name": "X", "email": "not-an-email", "password": "password123"},
    )
    assert res.status_code == 422


def test_login_success(client):
    email = _email()
    client.post(
        "/api/auth/signup",
        json={"name": "Carol", "email": email, "password": "password123"},
    )
    res = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password(client):
    email = _email()
    client.post(
        "/api/auth/signup",
        json={"name": "Dan", "email": email, "password": "password123"},
    )
    res = client.post("/api/auth/login", json={"email": email, "password": "wrongpass1"})
    assert res.status_code == 401


def test_login_unknown_email(client):
    res = client.post(
        "/api/auth/login",
        json={"email": _email(), "password": "password123"},
    )
    assert res.status_code == 401


def test_protected_route_requires_auth(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_protected_route_invalid_token(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert res.status_code == 401


def test_protected_route_valid_token(client, auth_headers):
    res = client.get("/api/auth/me", headers=auth_headers)
    assert res.status_code == 200
    assert "email" in res.json()


def test_protected_route_expired_token(client):
    import jwt
    from datetime import datetime, timedelta, timezone

    from app.core.config import settings

    expired = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000000",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert res.status_code == 401


def test_protected_route_wrong_scheme(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Token sometoken"})
    assert res.status_code == 401


def test_signup_concurrent_duplicate_returns_409(client, monkeypatch):
    """Simulate losing a signup race: the unique constraint maps to 409, not 500."""
    from sqlalchemy.exc import IntegrityError

    import app.services.auth_service as auth_service

    def losing_the_race(db, name, email, password):
        raise IntegrityError(
            "INSERT INTO users ...",
            {},
            Exception('duplicate key value violates unique constraint "users_email_key"'),
        )

    monkeypatch.setattr(auth_service, "create_user", losing_the_race)
    res = client.post(
        "/api/auth/signup",
        json={"name": "Racy", "email": _email(), "password": "password123"},
    )
    assert res.status_code == 409
    assert res.json()["detail"] == "Email already registered"
