"""create account_items table: inventário da conta, uma linha por unidade (07-progression §4.4, F4).

`account_morat_id`, `slot_name` e `system_slot` ficam vazios até a F6 (equipar).
"""

import sqlalchemy as sa
from alembic import op

revision = "0d72e556d5d3"
down_revision = "2100454de3ec"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("inventory_index", sa.Integer(), nullable=False),
        sa.Column("catalog_id", sa.Integer(), nullable=False),
        sa.Column("item_guid", sa.String(36), nullable=False),
        sa.Column("account_morat_id", sa.Integer(), nullable=True),
        sa.Column("slot_name", sa.String(20), nullable=True),
        sa.Column("system_slot", sa.Integer(), nullable=True),
        sa.Column("apply_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("apply_value", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="account_items_account_id_foreign"
        ),
        sa.ForeignKeyConstraint(
            ["account_morat_id"],
            ["account_morats.id"],
            name="account_items_account_morat_id_foreign",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "account_id", "inventory_index", name="account_items_account_id_inventory_index_unique"
        ),
        sa.UniqueConstraint("item_guid", name="account_items_item_guid_unique"),
        sa.UniqueConstraint(
            "account_morat_id", "slot_name", name="account_items_account_morat_id_slot_name_unique"
        ),
        sa.UniqueConstraint(
            "account_id", "system_slot", name="account_items_account_id_system_slot_unique"
        ),
    )
    op.create_index("account_items_account_morat_id_index", "account_items", ["account_morat_id"])


def downgrade() -> None:
    op.drop_index("account_items_account_morat_id_index", table_name="account_items")
    op.drop_table("account_items")
