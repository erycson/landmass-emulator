"""add banned_until to accounts: bloqueio temporário pela CLI (07-progression §5.13, D106)."""

import sqlalchemy as sa
from alembic import op

revision = "9e4c2b7a1d05"
down_revision = "4b7e1d2a9c60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.add_column(sa.Column("banned_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.drop_column("banned_until")
