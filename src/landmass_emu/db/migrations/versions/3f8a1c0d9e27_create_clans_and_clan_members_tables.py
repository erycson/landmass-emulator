"""create clans and clan_members tables: clã (F13, 07-progression §4.8, D55 a D61)."""

import sqlalchemy as sa
from alembic import op

revision = "3f8a1c0d9e27"
down_revision = "887ad86230f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=16), nullable=False),
        sa.Column("master_account_id", sa.Integer(), nullable=False),
        sa.Column("mark", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["master_account_id"], ["accounts.id"], name="clans_master_account_id_foreign"
        ),
        sa.UniqueConstraint("name", name="clans_name_unique"),
    )
    op.create_table(
        "clan_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clan_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("grade", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clan_id"], ["clans.id"], name="clan_members_clan_id_foreign"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="clan_members_account_id_foreign"
        ),
        sa.UniqueConstraint("account_id", name="clan_members_account_id_unique"),
    )
    op.create_index("clan_members_clan_id_index", "clan_members", ["clan_id"])


def downgrade() -> None:
    op.drop_index("clan_members_clan_id_index", table_name="clan_members")
    op.drop_table("clan_members")
    op.drop_table("clans")
