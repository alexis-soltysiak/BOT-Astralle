from alembic import op
import sqlalchemy as sa


revision = "0011_tracked_player_discord_link"
down_revision = "0010_match_score"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tracked_player", sa.Column("discord_user_id", sa.String(length=32), nullable=True))
    op.add_column("tracked_player", sa.Column("discord_display_name", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("tracked_player", "discord_display_name")
    op.drop_column("tracked_player", "discord_user_id")
