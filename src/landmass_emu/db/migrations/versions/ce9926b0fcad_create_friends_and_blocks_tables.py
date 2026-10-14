"""create friends and blocks tables: amizades e bloqueios (F12, 07-progression §4.7, D11)."""

import sqlalchemy as sa
from alembic import op

revision = "ce9926b0fcad"
down_revision = "ff38814bc227"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _create_relation("friends", "friend_account_id")
    _create_relation("blocks", "blocked_account_id")


def downgrade() -> None:
    op.drop_table("blocks")
    op.drop_table("friends")


def _create_relation(table: str, target: str) -> None:
    """Relação dirigida de `accounts` para `accounts`. Sem log: só o par e as datas."""
    op.create_table(
        table,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column(target, sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name=f"{table}_account_id_foreign"
        ),
        sa.ForeignKeyConstraint([target], ["accounts.id"], name=f"{table}_{target}_foreign"),
        sa.UniqueConstraint("account_id", target, name=f"{table}_account_id_{target}_unique"),
    )
    op.create_index(f"{table}_{target}_index", table, [target])
