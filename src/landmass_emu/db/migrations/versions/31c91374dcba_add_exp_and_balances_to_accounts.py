"""add total_exp, ld and cash to accounts: exp e saldos (F3, 07-progression §4.3, R-MON-01)."""

import sqlalchemy as sa
from alembic import op

revision = "31c91374dcba"
down_revision = "01ad613f288a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        for name in ("total_exp", "ld", "cash"):
            batch.add_column(sa.Column(name, sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        for name in ("cash", "ld", "total_exp"):
            batch.drop_column(name)
