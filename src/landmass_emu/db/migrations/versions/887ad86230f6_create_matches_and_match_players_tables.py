"""create matches and match_players tables: histórico de partidas (04-persistence)."""

import sqlalchemy as sa
from alembic import op

revision = "887ad86230f6"
down_revision = "ce9926b0fcad"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("map_record_id", sa.Integer(), nullable=False),
        sa.Column("map_file", sa.String(64), nullable=False),
        sa.Column("game_mode", sa.Integer(), nullable=False),
        sa.Column("game_class", sa.String(64), nullable=False),
        sa.Column("team_count", sa.Integer(), nullable=False),
        sa.Column("max_players", sa.Integer(), nullable=False),
        sa.Column("time_limit", sa.Integer(), nullable=False),
        sa.Column("goal_score", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_reason", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "match_players",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("nickname", sa.String(16), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("team", sa.Integer(), nullable=True),
        sa.Column("is_master", sa.Boolean(), nullable=False),
        sa.Column("kills", sa.Integer(), nullable=True),
        sa.Column("deaths", sa.Integer(), nullable=True),
        sa.Column("assists", sa.Integer(), nullable=True),
        sa.Column("ranking", sa.Integer(), nullable=True),
        sa.Column("played_percent", sa.Float(), nullable=True),
        sa.Column("won", sa.Boolean(), nullable=True),
        sa.Column("headshots", sa.Integer(), nullable=True),
        sa.Column("bullets", sa.Integer(), nullable=True),
        sa.Column("hits", sa.Integer(), nullable=True),
        sa.Column("damage", sa.Integer(), nullable=True),
        sa.Column("exp", sa.Integer(), nullable=True),
        sa.Column("money", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["match_id"], ["matches.id"], name="match_players_match_id_foreign"
        ),
        sa.UniqueConstraint(
            "match_id", "account_id", name="match_players_match_id_account_id_unique"
        ),
    )


def downgrade() -> None:
    op.drop_table("match_players")
    op.drop_table("matches")
