"""add access_level to accounts: nível de acesso GM (ucAccess do cliente, D193).

Contas existentes entram com 0 (jogador). Nenhum dado é apagado.
"""

import sqlalchemy as sa
from alembic import op

revision = "7a2d9c4e1b35"
down_revision = "e8b4d1f6a237"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("access_level", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.drop_column("access_level")
