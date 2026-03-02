from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_match_timestamps_bigint"
down_revision = "0007_matches_publications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("match", "game_start_ts", existing_type=sa.Integer(), type_=sa.BigInteger(), nullable=True)
    op.alter_column("match", "game_end_ts", existing_type=sa.Integer(), type_=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    op.alter_column("match", "game_end_ts", existing_type=sa.BigInteger(), type_=sa.Integer(), nullable=True)
    op.alter_column("match", "game_start_ts", existing_type=sa.BigInteger(), type_=sa.Integer(), nullable=True)