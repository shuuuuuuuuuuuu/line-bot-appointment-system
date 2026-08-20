"""add line_contacts for coupon eligibility picker

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-20 15:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "line_contacts" in set(inspector.get_table_names()):
        return

    op.create_table(
        "line_contacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("line_user_id", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False, server_default=""),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.UniqueConstraint("line_user_id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_line_contacts_line_user_id", "line_contacts", ["line_user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "line_contacts" not in set(inspector.get_table_names()):
        return
    op.drop_index("ix_line_contacts_line_user_id", table_name="line_contacts")
    op.drop_table("line_contacts")
