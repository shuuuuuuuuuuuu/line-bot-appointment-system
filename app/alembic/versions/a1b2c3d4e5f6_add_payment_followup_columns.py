# add payment followup columns

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "38ce518b7cbe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("payment_deadline_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "appointments",
        sa.Column(
            "payment_proof_received",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "appointments",
        sa.Column(
            "payment_reminder_sent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "appointments",
        sa.Column(
            "owner_notified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("appointments", "owner_notified")
    op.drop_column("appointments", "payment_reminder_sent")
    op.drop_column("appointments", "payment_proof_received")
    op.drop_column("appointments", "payment_deadline_at")
