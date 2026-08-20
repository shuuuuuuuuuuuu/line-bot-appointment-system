"""add business weekly hours and date overrides

Revision ID: f2a3b4c5d6e7
Revises: d0e1f2a3b4c5
Create Date: 2026-08-20 16:00:00.000000
"""
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _parse_off_weekdays(raw: str) -> list[int]:
    try:
        parsed = json.loads(raw or "[]")
        if isinstance(parsed, list):
            return [int(x) for x in parsed if 0 <= int(x) <= 6]
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return [4, 5, 6]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "business_weekly_hours" not in existing_tables:
        op.create_table(
            "business_weekly_hours",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("weekday", sa.Integer(), nullable=False),
            sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("open_hour", sa.Integer(), nullable=False, server_default="9"),
            sa.Column("close_hour", sa.Integer(), nullable=False, server_default="21"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.UniqueConstraint("weekday", name="uq_business_weekly_hours_weekday"),
        )
        op.create_index(
            "ix_business_weekly_hours_weekday",
            "business_weekly_hours",
            ["weekday"],
        )

    if "business_date_overrides" not in existing_tables:
        op.create_table(
            "business_date_overrides",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("target_date", sa.Date(), nullable=False),
            sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("open_hour", sa.Integer(), nullable=True),
            sa.Column("close_hour", sa.Integer(), nullable=True),
            sa.Column("note", sa.String(length=100), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.UniqueConstraint("target_date", name="uq_business_date_overrides_target_date"),
        )
        op.create_index(
            "ix_business_date_overrides_target_date",
            "business_date_overrides",
            ["target_date"],
        )

    settings_row = bind.execute(
        sa.text(
            "SELECT open_hour, close_hour, off_weekdays "
            "FROM business_settings ORDER BY id ASC LIMIT 1"
        )
    ).mappings().first()

    open_hour = int(settings_row["open_hour"]) if settings_row else 9
    close_hour = int(settings_row["close_hour"]) if settings_row else 21
    off_weekdays = (
        _parse_off_weekdays(settings_row["off_weekdays"])
        if settings_row
        else [4, 5, 6]
    )

    existing_weekly = bind.execute(
        sa.text("SELECT COUNT(*) AS cnt FROM business_weekly_hours")
    ).scalar()
    if not existing_weekly:
        for weekday in range(7):
            is_open = weekday not in off_weekdays
            bind.execute(
                sa.text(
                    "INSERT INTO business_weekly_hours "
                    "(weekday, is_open, open_hour, close_hour) "
                    "VALUES (:weekday, :is_open, :open_hour, :close_hour)"
                ),
                {
                    "weekday": weekday,
                    "is_open": 1 if is_open else 0,
                    "open_hour": open_hour,
                    "close_hour": close_hour,
                },
            )

    holidays = bind.execute(
        sa.text("SELECT holiday_date, name FROM business_holidays")
    ).mappings().all()
    for holiday in holidays:
        existing = bind.execute(
            sa.text(
                "SELECT id FROM business_date_overrides "
                "WHERE target_date = :target_date"
            ),
            {"target_date": holiday["holiday_date"]},
        ).first()
        if existing:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO business_date_overrides "
                "(target_date, is_open, open_hour, close_hour, note) "
                "VALUES (:target_date, 0, NULL, NULL, :note)"
            ),
            {
                "target_date": holiday["holiday_date"],
                "note": holiday["name"],
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "business_date_overrides" in existing_tables:
        op.drop_index("ix_business_date_overrides_target_date", table_name="business_date_overrides")
        op.drop_table("business_date_overrides")

    if "business_weekly_hours" in existing_tables:
        op.drop_index("ix_business_weekly_hours_weekday", table_name="business_weekly_hours")
        op.drop_table("business_weekly_hours")
