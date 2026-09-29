"""Add bookings.appointment_at + unique payments.provider_ref.

Revision ID: 0002_booking_appointment
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_booking_appointment"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column("appointment_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill existing rows (if any) so the column can become NOT NULL.
    op.execute("UPDATE bookings SET appointment_at = now() WHERE appointment_at IS NULL")
    op.alter_column("bookings", "appointment_at", nullable=False)
    op.create_unique_constraint(
        "uq_payments_provider_ref", "payments", ["provider_ref"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_payments_provider_ref", "payments", type_="unique")
    op.drop_column("bookings", "appointment_at")
