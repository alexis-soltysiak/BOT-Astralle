from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012_live_game_ranked_snapshot"
down_revision = "0011_tracked_player_discord_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "live_game_ranked_snapshot",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tracked_player_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tracked_player.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(length=16), nullable=True),
        sa.Column("game_id", sa.String(length=32), nullable=False),
        sa.Column("queue_type", sa.String(length=32), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=True),
        sa.Column("division", sa.String(length=8), nullable=True),
        sa.Column("league_points", sa.Integer(), nullable=True),
        sa.Column("wins", sa.Integer(), nullable=True),
        sa.Column("losses", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "tracked_player_id",
            "game_id",
            "queue_type",
            name="uq_live_game_ranked_snapshot",
        ),
    )


def downgrade() -> None:
    op.drop_table("live_game_ranked_snapshot")
