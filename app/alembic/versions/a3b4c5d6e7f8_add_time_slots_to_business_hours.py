"""add time_slots to business hours

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-08-20 16:40:00.000000
"""
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _slot_json(open_hour, close_hour):
    return json.dumps([{"open_hour": int(open_hour), "close_hour": int(close_hour)}])


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    weekly_columns = {col["name"] for col in inspector.get_columns("business_weekly_hours")}
    if "time_slots" not in weekly_columns:
        op.add_column(
            "business_weekly_hours",
            sa.Column("time_slots", sa.String(length=512), nullable=False, server_default="[]"),
        )

    override_columns = {col["name"] for col in inspector.get_columns("business_date_overrides")}
    if "time_slots" not in override_columns:
        op.add_column(
            "business_date_overrides",
            sa.Column("time_slots", sa.String(length=512), nullable=False, server_default="[]"),
        )

    weekly_rows = bind.execute(sa.text("SELECT id, open_hour, close_hour FROM business_weekly_hours")).mappings().all()
    for row in weekly_rows:
        bind.execute(
            sa.text("UPDATE business_weekly_hours SET time_slots=:slots WHERE id=:id"),
            {"id": row["id"], "slots": _slot_json(row["open_hour"], row["close_hour"])},
        )

    override_rows = bind.execute(
        sa.text("SELECT id, is_open, open_hour, close_hour FROM business_date_overrides")
    ).mappings().all()
    for row in override_rows:
        slots = "[]"
        if row["is_open"] and row["open_hour"] is not None and row["close_hour"] is not None:
            slots = _slot_json(row["open_hour"], row["close_hour"])
        bind.execute(
            sa.text("UPDATE business_date_overrides SET time_slots=:slots WHERE id=:id"),
            {"id": row["id"], "slots": slots},
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    weekly_columns = {col["name"] for col in inspector.get_columns("business_weekly_hours")}
    if "time_slots" in weekly_columns:
        op.drop_column("business_weekly_hours", "time_slots")

    override_columns = {col["name"] for col in inspector.get_columns("business_date_overrides")}
    if "time_slots" in override_columns:
        op.drop_column("business_date_overrides", "time_slots")
