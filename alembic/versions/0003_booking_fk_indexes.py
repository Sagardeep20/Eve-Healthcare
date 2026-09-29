"""Sync bookings FK indexes declared in the model (index=True).

Revision ID: 0003_booking_fk_indexes
Revises: 0002_booking_appointment
"""

from alembic import op


revision = "0003_booking_fk_indexes"
down_revision = "0002_booking_appointment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_bookings_centre_id", "bookings", ["centre_id"])
    op.create_index("ix_bookings_test_id", "bookings", ["test_id"])


def downgrade() -> None:
    op.drop_index("ix_bookings_test_id", table_name="bookings")
    op.drop_index("ix_bookings_centre_id", table_name="bookings")
