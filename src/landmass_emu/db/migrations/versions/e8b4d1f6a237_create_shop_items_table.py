"""create shop_items table: venda da loja (D191), um item por id do catálogo com preço por nível.

Linhas vazias: nada à venda até o `landmass-emu shop sync`.
"""

import sqlalchemy as sa
from alembic import op

revision = "e8b4d1f6a237"
down_revision = "5c1e8a3f7b92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_items",
        sa.Column("catalog_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("point_0", sa.Integer(), server_default="0", nullable=False),
        sa.Column("point_1", sa.Integer(), server_default="0", nullable=False),
        sa.Column("point_2", sa.Integer(), server_default="0", nullable=False),
        sa.Column("point_3", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cash_0", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cash_1", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cash_2", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cash_3", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("catalog_id"),
    )


def downgrade() -> None:
    op.drop_table("shop_items")
