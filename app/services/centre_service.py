"""Centre/test read business logic."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest


def list_centres(db: Session) -> list[DiagnosticCentre]:
    return list(db.scalars(select(DiagnosticCentre).order_by(DiagnosticCentre.name)).all())


def get_centre(db: Session, centre_id: uuid.UUID) -> DiagnosticCentre | None:
    return db.get(DiagnosticCentre, centre_id)


def list_tests(db: Session) -> list[DiagnosticTest]:
    return list(db.scalars(select(DiagnosticTest).order_by(DiagnosticTest.name)).all())


def get_test(db: Session, test_id: uuid.UUID) -> DiagnosticTest | None:
    return db.get(DiagnosticTest, test_id)


def get_tests_for_centre(
    db: Session, centre_id: uuid.UUID
) -> tuple[DiagnosticCentre | None, list[tuple[DiagnosticTest, CentreTest]]]:
    centre = db.get(DiagnosticCentre, centre_id)
    if centre is None:
        return None, []
    rows = db.execute(
        select(DiagnosticTest, CentreTest)
        .join(CentreTest, CentreTest.test_id == DiagnosticTest.id)
        .where(CentreTest.centre_id == centre_id)
        .order_by(DiagnosticTest.name)
    ).all()
    return centre, rows
