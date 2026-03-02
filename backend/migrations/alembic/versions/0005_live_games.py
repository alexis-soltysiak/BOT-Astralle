from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_live_games"
down_revision = "0004_leaderboards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "live_game_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tracked_player_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tracked_player.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="none"),
        sa.Column("game_id", sa.String(length=32), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tracked_player_id", name="uq_live_game_state_player"),
    )


def downgrade() -> None:
    op.drop_table("live_game_state")