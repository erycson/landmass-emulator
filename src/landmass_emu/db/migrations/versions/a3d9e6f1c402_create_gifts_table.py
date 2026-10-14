"""create gifts table e gate_count em accounts: Depósito (F10) e gates do hangar (R-GATE-01)."""

import sqlalchemy as sa
from alembic import op

revision = "a3d9e6f1c402"
down_revision = "a3c7e915d2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gifts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sender_account_id", sa.Integer(), nullable=True),
        sa.Column("receiver_account_id", sa.Integer(), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("catalog_id", sa.Integer(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["sender_account_id"], ["accounts.id"], name="gifts_sender_account_id_foreign"
        ),
        sa.ForeignKeyConstraint(
            ["receiver_account_id"], ["accounts.id"], name="gifts_receiver_account_id_foreign"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("gifts_receiver_account_id_index", "gifts", ["receiver_account_id"])
    op.add_column(
        "accounts", sa.Column("gate_count", sa.Integer(), server_default="4", nullable=False)
    )


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.drop_column("gate_count")
    op.drop_index("gifts_receiver_account_id_index", table_name="gifts")
    op.drop_table("gifts")
