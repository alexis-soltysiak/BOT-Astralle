from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_matches_publications"
down_revision = "0006_ranked_snapshot_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("riot_match_id", sa.String(length=32), nullable=False),
        sa.Column("region", sa.String(length=16), nullable=False),
        sa.Column("queue_id", sa.Integer(), nullable=True),
        sa.Column("game_mode", sa.String(length=32), nullable=True),
        sa.Column("game_start_ts", sa.Integer(), nullable=True),
        sa.Column("game_end_ts", sa.Integer(), nullable=True),
        sa.Column("game_duration", sa.Integer(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("riot_match_id", name="uq_match_riot_match_id"),
    )

    op.create_index("ix_match_created_at", "match", ["created_at"], unique=False)

    op.create_table(
        "match_participant",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "match_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("match.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("puuid", sa.String(length=128), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("riot_id_game_name", sa.String(length=64), nullable=True),
        sa.Column("riot_id_tag_line", sa.String(length=16), nullable=True),
        sa.Column("champion_name", sa.String(length=64), nullable=True),
        sa.Column("kills", sa.Integer(), nullable=True),
        sa.Column("deaths", sa.Integer(), nullable=True),
        sa.Column("assists", sa.Integer(), nullable=True),
        sa.Column("win", sa.Boolean(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("match_id", "puuid", name="uq_match_participant_match_puuid"),
    )

    op.create_index("ix_match_participant_match_id", "match_participant", ["match_id"], unique=False)

    op.create_table(
        "publication_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("dedupe_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("claimed_by", sa.String(length=64), nullable=True),
        sa.Column("claimed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("dedupe_key", name="uq_publication_event_dedupe_key"),
    )

    op.create_index("ix_publication_event_status_available", "publication_event", ["status", "available_at"], unique=False)
    op.create_index("ix_publication_event_created_at", "publication_event", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_publication_event_created_at", table_name="publication_event")
    op.drop_index("ix_publication_event_status_available", table_name="publication_event")
    op.drop_table("publication_event")
    op.drop_index("ix_match_participant_match_id", table_name="match_participant")
    op.drop_table("match_participant")
    op.drop_index("ix_match_created_at", table_name="match")
    op.drop_table("match")