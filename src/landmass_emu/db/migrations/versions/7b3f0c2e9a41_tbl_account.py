"""tbl_account: contas de jogo (LM_account.sql, decisão D6)."""

import sqlalchemy as sa
from alembic import op

revision = "7b3f0c2e9a41"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tbl_account",
        sa.Column("account_code", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("userid", sa.String(12), nullable=False),
        sa.Column("nick", sa.String(16), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("create_date", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("userid", name="uq_tbl_account_userid"),
        sa.UniqueConstraint("nick", name="uq_tbl_account_nick"),
        sa.UniqueConstraint("token_hash", name="uq_tbl_account_token_hash"),
    )


def downgrade() -> None:
    op.drop_table("tbl_account")
