"""create account_morats table: morats da conta, um por gate (07-progression §4.5, F5).

Vem antes de `account_items`, que referencia esta tabela pela montagem de parte em morat.
"""

import sqlalchemy as sa
from alembic import op

revision = "2100454de3ec"
down_revision = "31c91374dcba"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_morats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("inventory_index", sa.Integer(), nullable=False),
        sa.Column("catalog_id", sa.Integer(), nullable=False),
        sa.Column("item_guid", sa.String(36), nullable=False),
        sa.Column("gate_index", sa.Integer(), nullable=True),
        sa.Column("apply_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("apply_value", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="account_morats_account_id_foreign"
        ),
        sa.UniqueConstraint(
            "account_id", "inventory_index", name="account_morats_account_id_inventory_index_unique"
        ),
        sa.UniqueConstraint("item_guid", name="account_morats_item_guid_unique"),
        sa.UniqueConstraint(
            "account_id", "gate_index", name="account_morats_account_id_gate_index_unique"
        ),
    )


def downgrade() -> None:
    op.drop_table("account_morats")
