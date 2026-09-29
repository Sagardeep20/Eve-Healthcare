"""Idempotent development seed data.

Run with: python -m app.seed
"""

from decimal import Decimal

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest

CENTRES = [
    {"name": "Apollo Diagnostics", "location": "Bangalore"},
    {"name": "Dr Lal PathLabs", "location": "Delhi"},
]

TESTS = [
    {"name": "CBC", "description": "Complete Blood Count"},
    {"name": "Thyroid Profile", "description": "T3, T4, TSH"},
    {"name": "Lipid Profile", "description": "Cholesterol panel"},
    {"name": "Blood Sugar (Fasting)", "description": "Fasting glucose"},
]

# (centre_name, test_name) -> price. Different centres charge different prices.
PRICES: dict[tuple[str, str], str] = {
    ("Apollo Diagnostics", "CBC"): "500.00",
    ("Apollo Diagnostics", "Thyroid Profile"): "900.00",
    ("Apollo Diagnostics", "Lipid Profile"): "1200.00",
    ("Dr Lal PathLabs", "CBC"): "450.00",
    ("Dr Lal PathLabs", "Thyroid Profile"): "850.00",
    ("Dr Lal PathLabs", "Blood Sugar (Fasting)"): "200.00",
}


def seed() -> None:
    db = SessionLocal()
    try:
        centres: dict[str, DiagnosticCentre] = {}
        for c in CENTRES:
            existing = db.scalar(
                select(DiagnosticCentre).where(DiagnosticCentre.name == c["name"])
            )
            if existing is None:
                existing = DiagnosticCentre(**c)
                db.add(existing)
                db.flush()
            centres[c["name"]] = existing

        tests: dict[str, DiagnosticTest] = {}
        for t in TESTS:
            existing = db.scalar(
                select(DiagnosticTest).where(DiagnosticTest.name == t["name"])
            )
            if existing is None:
                existing = DiagnosticTest(**t)
                db.add(existing)
                db.flush()
            tests[t["name"]] = existing

        for (centre_name, test_name), price in PRICES.items():
            centre = centres[centre_name]
            test = tests[test_name]
            existing = db.scalar(
                select(CentreTest).where(
                    CentreTest.centre_id == centre.id,
                    CentreTest.test_id == test.id,
                )
            )
            if existing is None:
                db.add(
                    CentreTest(
                        centre_id=centre.id,
                        test_id=test.id,
                        price=Decimal(price),
                    )
                )
            elif existing.price != Decimal(price):
                existing.price = Decimal(price)

        db.commit()
        print("Seed completed: centres=%d tests=%d prices=%d" % (len(centres), len(tests), len(PRICES)))
    finally:
        db.close()


if __name__ == "__main__":
    seed()
