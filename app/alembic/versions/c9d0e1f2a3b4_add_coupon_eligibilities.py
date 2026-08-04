"""add coupon eligibilities

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-08-02 16:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "coupon_eligibilities" not in tables:
        op.create_table(
            "coupon_eligibilities",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "coupon_id", sa.Integer(), sa.ForeignKey("coupons.id"), nullable=False
            ),
            sa.Column("line_user_id", sa.String(length=50), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.UniqueConstraint(
                "coupon_id", "line_user_id", name="uq_coupon_eligibility"
            ),
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index(
            "ix_coupon_eligibilities_coupon_id", "coupon_eligibilities", ["coupon_id"]
        )
        op.create_index(
            "ix_coupon_eligibilities_line_user_id",
            "coupon_eligibilities",
            ["line_user_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "coupon_eligibilities" not in tables:
        return
    op.drop_index(
        "ix_coupon_eligibilities_line_user_id", table_name="coupon_eligibilities"
    )
    op.drop_index("ix_coupon_eligibilities_coupon_id", table_name="coupon_eligibilities")
    op.drop_table("coupon_eligibilities")
