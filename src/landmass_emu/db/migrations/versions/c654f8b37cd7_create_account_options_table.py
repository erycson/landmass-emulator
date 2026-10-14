"""create account_options table: opções do jogador (LM_REGISTER_INFO, D11, 07-progression §4.6)."""

import sqlalchemy as sa
from alembic import op

revision = "c654f8b37cd7"
down_revision = "d511fd6ac388"
branch_labels = None
depends_on = None

# Ordem de LM_REGISTER_INFO (tools/re/message_server.md §4.1). A ordem é o contrato com o cliente.
OPTIONS = (
    "background",
    "effect",
    "voice_info",
    "voice_character",
    "mouse_acc",
    "mouse_sensitivity",
    "mouse_invert",
    "weapon_1",
    "weapon_2",
    "weapon_3",
    "weapon_4",
    "weapon_5",
    "weapon_6",
    "weapon_7",
    "weapon_8",
    "weapon_9",
    "weapon_0",
    "move_forward",
    "move_backward",
    "move_left",
    "move_right",
    "fire",
    "alt_fire",
    "walk",
    "down",
    "jump",
    "change_mag",
    "chaff",
    "booster",
    "action",
    "speech_menu_1",
    "speech_menu_2",
    "speech_menu_3",
    "object",
    "mirror",
    "minimap",
    "screenshot",
)


def upgrade() -> None:
    op.create_table(
        "account_options",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        *(sa.Column(name, sa.Integer(), nullable=False, server_default="0") for name in OPTIONS),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="account_options_account_id_foreign"
        ),
        sa.UniqueConstraint("account_id", name="account_options_account_id_unique"),
    )


def downgrade() -> None:
    op.drop_table("account_options")
