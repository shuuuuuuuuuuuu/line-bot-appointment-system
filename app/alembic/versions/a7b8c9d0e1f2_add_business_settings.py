"""add business settings and holidays

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-24 15:40:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("open_hour", sa.Integer(), nullable=False, server_default="9"),
        sa.Column("close_hour", sa.Integer(), nullable=False, server_default="21"),
        sa.Column("slot_interval_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("buffer_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("off_weekdays", sa.String(length=64), nullable=False, server_default="[4,5,6]"),
        sa.Column("max_advance_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("slot_lock_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
    )
    op.create_table(
        "business_holidays",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.UniqueConstraint("holiday_date", name="uq_business_holiday_date"),
    )
    op.create_index("ix_business_holidays_holiday_date", "business_holidays", ["holiday_date"])

    op.execute(
        sa.text(
            "INSERT INTO business_settings "
            "(open_hour, close_hour, slot_interval_minutes, buffer_minutes, "
            "off_weekdays, max_advance_days, slot_lock_minutes) "
            "VALUES (9, 21, 60, 60, '[4,5,6]', 30, 10)"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_business_holidays_holiday_date", table_name="business_holidays")
    op.drop_table("business_holidays")
    op.drop_table("business_settings")
