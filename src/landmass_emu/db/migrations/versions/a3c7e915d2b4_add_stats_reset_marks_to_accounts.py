"""add record_reset_at and combat_reset_at to accounts: marcos de zerado (D131, D132).

Ficha derivada de `match_players` só conta partidas depois destes marcos. Nulo = nunca zerado.
"""

import sqlalchemy as sa
from alembic import op

revision = "a3c7e915d2b4"
down_revision = "9e4c2b7a1d05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.add_column(sa.Column("record_reset_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("combat_reset_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.drop_column("combat_reset_at")
        batch.drop_column("record_reset_at")
