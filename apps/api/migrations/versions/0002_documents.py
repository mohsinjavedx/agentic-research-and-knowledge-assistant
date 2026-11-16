"""Create durable document status for crash recovery."""

import sqlalchemy as sa
from alembic import op

revision = "0002_documents"
down_revision = "0001_pgvector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("is_sample", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), server_default="queued", nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('queued','processing','ready','failed')", name="ck_documents_status"
        ),
        sa.CheckConstraint("is_sample OR session_id IS NOT NULL", name="ck_documents_owner"),
        sa.CheckConstraint(
            "page_count IS NULL OR page_count BETWEEN 1 AND 100", name="ck_documents_pages"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_status_updated_at", "documents", ["status", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_documents_status_updated_at", table_name="documents")
    op.drop_table("documents")
