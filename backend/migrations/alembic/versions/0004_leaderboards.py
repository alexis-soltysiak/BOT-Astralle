from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_leaderboards"
down_revision = "0003_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tracked_player", sa.Column("platform", sa.String(length=16), nullable=True))

    op.create_table(
        "ranked_snapshot",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tracked_player_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tracked_player.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("summoner_id", sa.String(length=128), nullable=False),
        sa.Column("queue_type", sa.String(length=32), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=True),
        sa.Column("division", sa.String(length=8), nullable=True),
        sa.Column("league_points", sa.Integer(), nullable=True),
        sa.Column("wins", sa.Integer(), nullable=True),
        sa.Column("losses", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_index(
        "ix_ranked_snapshot_player_queue_fetched",
        "ranked_snapshot",
        ["tracked_player_id", "queue_type", "fetched_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ranked_snapshot_player_queue_fetched", table_name="ranked_snapshot")
    op.drop_table("ranked_snapshot")
    op.drop_column("tracked_player", "platform")