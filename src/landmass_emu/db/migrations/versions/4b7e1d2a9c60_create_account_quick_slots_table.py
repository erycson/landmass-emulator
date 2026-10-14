"""create account_quick_slots table: atalhos da conta (tbl_quickslot do SQL antigo, D73).

Cinco linhas por conta, semeadas na criação e no `account kit apply`. Sem opcode no cliente: só
gravadas (tools/re/features.md §4).
"""

import sqlalchemy as sa
from alembic import op

revision = "4b7e1d2a9c60"
down_revision = "3f8a1c0d9e27"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_quick_slots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("slot_index", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("memo", sa.String(8), nullable=False, server_default=""),
        sa.Column("gate_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="account_quick_slots_account_id_foreign"
        ),
        sa.UniqueConstraint(
            "account_id", "slot_index", name="account_quick_slots_account_id_slot_index_unique"
        ),
    )


def downgrade() -> None:
    op.drop_table("account_quick_slots")
