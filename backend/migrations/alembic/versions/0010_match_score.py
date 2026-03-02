from alembic import op
import sqlalchemy as sa


revision = "0010_match_score"
down_revision = "0009_discord_message_bindings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_score",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("match_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("puuid", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("final_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("final_grade", sa.String(length=4), nullable=False),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["match.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("match_id", "puuid", name="uq_match_score_match_puuid"),
    )


def downgrade() -> None:
    op.drop_table("match_score")