from __future__ import annotations

from alembic import op

revision = "0006_ranked_snapshot_nullable"
down_revision = "0005_live_games"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("ranked_snapshot", "summoner_id", nullable=True)


def downgrade() -> None:
    op.alter_column("ranked_snapshot", "summoner_id", nullable=False)
