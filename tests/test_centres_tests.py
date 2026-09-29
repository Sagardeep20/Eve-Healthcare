"""Centre/test catalogue tests."""

import uuid


def test_list_centres(client):
    res = client.get("/api/centres")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_get_centre(client, db_session):
    from app.models.centre import DiagnosticCentre
    from sqlalchemy import select

    centre = db_session.scalar(select(DiagnosticCentre))
    res = client.get(f"/api/centres/{centre.id}")
    assert res.status_code == 200
    assert res.json()["name"] == centre.name


def test_get_centre_invalid_id(client):
    assert client.get("/api/centres/not-a-uuid").status_code == 404
    assert client.get(f"/api/centres/{uuid.uuid4()}").status_code == 404


def test_list_tests(client):
    res = client.get("/api/tests")
    assert res.status_code == 200
    names = {t["name"] for t in res.json()}
    assert {"CBC", "Thyroid Profile"} <= names


def test_get_test(client, db_session):
    from app.models.test import DiagnosticTest
    from sqlalchemy import select

    test = db_session.scalar(select(DiagnosticTest))
    res = client.get(f"/api/tests/{test.id}")
    assert res.status_code == 200
    assert res.json()["name"] == test.name


def test_get_test_invalid_id(client):
    assert client.get("/api/tests/not-a-uuid").status_code == 404
    assert client.get(f"/api/tests/{uuid.uuid4()}").status_code == 404


def test_get_centre_tests_returns_centre_specific_prices(client, db_session):
    from app.models.centre import DiagnosticCentre
    from sqlalchemy import select

    centres = db_session.scalars(select(DiagnosticCentre)).all()
    by_name = {c.name: c for c in centres}

    apollo = client.get(f"/api/centres/{by_name['Apollo Diagnostics'].id}/tests")
    assert apollo.status_code == 200
    prices = {t["name"]: t["price"] for t in apollo.json()["tests"]}
    assert len(prices) == 2
    assert float(prices["CBC"]) == 500.00

    lal = client.get(f"/api/centres/{by_name['Dr Lal PathLabs'].id}/tests")
    assert lal.status_code == 200
    lal_prices = {t["name"]: t["price"] for t in lal.json()["tests"]}
    # Same test, different centre price -> proves centre-specific pricing.
    assert float(lal_prices["CBC"]) == 450.00


def test_get_centre_tests_invalid_centre(client):
    assert client.get("/api/centres/not-a-uuid/tests").status_code == 404
    assert client.get(f"/api/centres/{uuid.uuid4()}/tests").status_code == 404
