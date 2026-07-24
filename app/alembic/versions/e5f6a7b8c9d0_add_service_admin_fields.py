"""add service admin fields

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-23 12:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "services",
        sa.Column("price", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "services",
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"),
    )
    op.add_column(
        "services",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "services",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )

    # 依現有分類回填預設價格／時長，並用 id 當初始排序
    conn = op.get_bind()
    services = conn.execute(
        sa.text("SELECT id, category_id FROM services ORDER BY id")
    ).fetchall()
    for service_id, category_id in services:
        if category_id == 2:
            price, duration = 3333, 70
        elif category_id == 3:
            price, duration = 1555, 90
        else:
            price, duration = 2222, 60
        conn.execute(
            sa.text(
                "UPDATE services SET price=:price, duration_minutes=:duration, "
                "sort_order=:sort_order WHERE id=:id"
            ),
            {
                "price": price,
                "duration": duration,
                "sort_order": service_id,
                "id": service_id,
            },
        )


def downgrade() -> None:
    op.drop_column("services", "sort_order")
    op.drop_column("services", "is_active")
    op.drop_column("services", "duration_minutes")
    op.drop_column("services", "price")
