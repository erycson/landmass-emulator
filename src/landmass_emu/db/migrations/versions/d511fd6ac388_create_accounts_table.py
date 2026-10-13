"""create accounts table: contas de jogo (LM_account.sql, convenção Laravel, D11)."""

import sqlalchemy as sa
from alembic import op

revision = "d511fd6ac388"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(12), nullable=False),
        sa.Column("nickname", sa.String(16), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("username", name="accounts_username_unique"),
        sa.UniqueConstraint("nickname", name="accounts_nickname_unique"),
        sa.UniqueConstraint("token_hash", name="accounts_token_hash_unique"),
    )


def downgrade() -> None:
    op.drop_table("accounts")
