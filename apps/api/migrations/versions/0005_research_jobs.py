"""Persist bounded session-scoped research jobs."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_research_jobs"
down_revision = "0004_session_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("document_ids", postgresql.JSONB(), nullable=False),
        sa.Column("top_k", sa.Integer(), server_default=sa.text("5"), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column(
            "steps",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "tool_calls",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("iterations", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("tool_calls_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("sufficiency_verdict", sa.Boolean(), nullable=True),
        sa.Column("report", postgresql.JSONB(), nullable=True),
        sa.Column(
            "evidence",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed')",
            name="ck_research_jobs_status",
        ),
        sa.CheckConstraint("iterations BETWEEN 0 AND 4", name="ck_research_jobs_iterations"),
        sa.CheckConstraint("tool_calls_count BETWEEN 0 AND 6", name="ck_research_jobs_tool_calls"),
        sa.CheckConstraint("top_k BETWEEN 1 AND 10", name="ck_research_jobs_top_k"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_jobs_session_created",
        "research_jobs",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_jobs_session_created", table_name="research_jobs")
    op.drop_table("research_jobs")
