from alembic import op
import sqlalchemy as sa


revision = "0009_discord_message_bindings"
down_revision = "0008_match_timestamps_bigint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discord_message_binding",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column(
            "binding_key",
            sa.Enum("LEADERBOARD_MESSAGE", "LIVE_GAMES_MESSAGE", "FINISHED_GAMES_CHANNEL", name="discordbindingkey"),
            nullable=False,
        ),
        sa.Column("channel_id", sa.String(length=32), nullable=False),
        sa.Column("message_id", sa.String(length=32), nullable=True),
        sa.Column("leaderboard_mode", sa.Enum("solo", "flex", name="leaderboardmode"), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id", "binding_key", name="uq_discord_binding_guild_key"),
    )


def downgrade() -> None:
    op.drop_table("discord_message_binding")
    op.execute("DROP TYPE IF EXISTS leaderboardmode")
    op.execute("DROP TYPE IF EXISTS discordbindingkey")