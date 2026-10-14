"""add password_hash to accounts: senha do login por formulário (D240).

Contas existentes ficam sem senha (nulo): continuam entrando só pelo token. Nenhum dado é apagado.
"""

import sqlalchemy as sa
from alembic import op

revision = "b3e8f1a6c924"
down_revision = "7a2d9c4e1b35"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("password_hash", sa.String(128), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.drop_column("password_hash")
