"""add coupon category_id

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-08-04 14:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    coupon_cols = {col["name"] for col in inspector.get_columns("coupons")}
    if "category_id" in coupon_cols:
        return

    op.add_column("coupons", sa.Column("category_id", sa.Integer(), nullable=True))

    # Backfill from service_slug → category name keywords
    slug_map = {
        "soundhealing": "%頌缽%",
        "sound_healing": "%頌缽%",
        "reiki": "%靈氣%",
        "akashic": "%阿卡西%",
        "akashi": "%阿卡西%",
    }
    for slug, pattern in slug_map.items():
        bind.execute(
            text(
                """
                UPDATE coupons c
                SET category_id = (
                    SELECT id FROM categories
                    WHERE category_name LIKE :pattern
                    LIMIT 1
                )
                WHERE c.service_slug = :slug AND c.category_id IS NULL
                """
            ),
            {"pattern": pattern, "slug": slug},
        )

    # Fallback: any remaining coupons get first category
    bind.execute(
        text(
            """
            UPDATE coupons
            SET category_id = (SELECT id FROM categories ORDER BY id ASC LIMIT 1)
            WHERE category_id IS NULL
            """
        )
    )

    op.alter_column(
        "coupons",
        "category_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_coupons_category_id",
        "coupons",
        "categories",
        ["category_id"],
        ["id"],
    )
    op.create_index("ix_coupons_category_id", "coupons", ["category_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    coupon_cols = {col["name"] for col in inspector.get_columns("coupons")}
    if "category_id" not in coupon_cols:
        return
    op.drop_index("ix_coupons_category_id", table_name="coupons")
    op.drop_constraint("fk_coupons_category_id", "coupons", type_="foreignkey")
    op.drop_column("coupons", "category_id")
