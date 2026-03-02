from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_tracked_players"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tracked_player",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("region", sa.String(length=16), nullable=False),
        sa.Column("game_name", sa.String(length=64), nullable=False),
        sa.Column("tag_line", sa.String(length=16), nullable=False),
        sa.Column("puuid", sa.String(length=128), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("region", "game_name", "tag_line", name="uq_tracked_player_riot_id"),
        sa.UniqueConstraint("puuid", name="uq_tracked_player_puuid"),
    )


def downgrade() -> None:
    op.drop_table("tracked_player")