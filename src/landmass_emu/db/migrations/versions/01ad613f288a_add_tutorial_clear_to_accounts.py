"""add tutorial_clear to accounts: máscara do tutorial (F2, 07-progression §4.3, R-TUT-01)."""

import sqlalchemy as sa
from alembic import op

revision = "01ad613f288a"
down_revision = "c654f8b37cd7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.add_column(
            sa.Column("tutorial_clear", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.drop_column("tutorial_clear")
