"""Persistent sliding-window request admission events."""

import sqlalchemy as sa
from alembic import op

revision = "0006_rate_limit_events"
down_revision = "0005_research_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("session_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("action IN ('chat','research','upload')", name="ck_rate_limit_action"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rate_limit_ip_window", "rate_limit_events", ["action", "ip_hash", "created_at"]
    )
    op.create_index(
        "ix_rate_limit_session_window",
        "rate_limit_events",
        ["action", "session_hash", "created_at"],
    )
    op.create_index("ix_rate_limit_expiry", "rate_limit_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("rate_limit_events")
