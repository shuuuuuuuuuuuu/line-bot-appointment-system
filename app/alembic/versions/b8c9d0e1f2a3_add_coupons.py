"""add coupons and redemptions

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-02 15:55:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "coupons" not in tables:
        op.create_table(
            "coupons",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("code", sa.String(length=100), nullable=False),
            sa.Column("discount_percent", sa.Integer(), nullable=False),
            sa.Column("service_slug", sa.String(length=50), nullable=False),
            sa.Column("valid_from", sa.Date(), nullable=False),
            sa.Column("valid_to", sa.Date(), nullable=False),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
            ),
            sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.UniqueConstraint("code"),
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index("ix_coupons_id", "coupons", ["id"])
        op.create_index("ix_coupons_code", "coupons", ["code"])

    if "coupon_redemptions" not in tables:
        op.create_table(
            "coupon_redemptions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "coupon_id", sa.Integer(), sa.ForeignKey("coupons.id"), nullable=False
            ),
            sa.Column("line_user_id", sa.String(length=50), nullable=False),
            sa.Column(
                "appointment_id",
                sa.Integer(),
                sa.ForeignKey("appointments.id"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index(
            "ix_coupon_redemptions_coupon_id", "coupon_redemptions", ["coupon_id"]
        )
        op.create_index(
            "ix_coupon_redemptions_line_user_id",
            "coupon_redemptions",
            ["line_user_id"],
        )

    appointment_cols = {col["name"] for col in inspector.get_columns("appointments")}
    if "coupon_code" not in appointment_cols:
        op.add_column(
            "appointments",
            sa.Column("coupon_code", sa.String(length=100), nullable=True),
        )
    if "original_price" not in appointment_cols:
        op.add_column(
            "appointments",
            sa.Column("original_price", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    appointment_cols = {col["name"] for col in inspector.get_columns("appointments")}

    if "original_price" in appointment_cols:
        op.drop_column("appointments", "original_price")
    if "coupon_code" in appointment_cols:
        op.drop_column("appointments", "coupon_code")

    if "coupon_redemptions" in tables:
        op.drop_index(
            "ix_coupon_redemptions_line_user_id", table_name="coupon_redemptions"
        )
        op.drop_index("ix_coupon_redemptions_coupon_id", table_name="coupon_redemptions")
        op.drop_table("coupon_redemptions")

    if "coupons" in tables:
        op.drop_index("ix_coupons_code", table_name="coupons")
        op.drop_index("ix_coupons_id", table_name="coupons")
        op.drop_table("coupons")
