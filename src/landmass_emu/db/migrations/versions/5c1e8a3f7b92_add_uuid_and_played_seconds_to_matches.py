"""add uuid to matches and played_seconds to match_players: id da partida e tempo jogado.

Linhas antigas ficam com `uuid` e `played_seconds` nulos: não há dado para preencher.
"""

import sqlalchemy as sa
from alembic import op

revision = "5c1e8a3f7b92"
down_revision = "a3d9e6f1c402"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("matches") as batch:
        batch.add_column(sa.Column("uuid", sa.String(36), nullable=True))
        batch.create_unique_constraint("matches_uuid_unique", ["uuid"])
    with op.batch_alter_table("match_players") as batch:
        batch.add_column(sa.Column("played_seconds", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("match_players") as batch:
        batch.drop_column("played_seconds")
    with op.batch_alter_table("matches") as batch:
        batch.drop_constraint("matches_uuid_unique", type_="unique")
        batch.drop_column("uuid")
