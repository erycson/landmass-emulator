"""add regular columns to accounts: nest e classe de 105 (07-progression §4.3, F5)."""

import sqlalchemy as sa
from alembic import op

revision = "ff38814bc227"
down_revision = "0d72e556d5d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("regular_nest_id", sa.Integer(), nullable=True))
    op.add_column("accounts", sa.Column("regular_morat_class", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.drop_column("regular_morat_class")
        batch.drop_column("regular_nest_id")
