"""Make session indexing idempotent by document checksum."""

import sqlalchemy as sa
from alembic import op

revision = "0004_session_lifecycle"
down_revision = "0003_chunk_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_documents_session_checksum",
        "documents",
        ["session_id", "checksum"],
        unique=True,
        postgresql_where=sa.text("NOT is_sample AND session_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_documents_session_checksum", table_name="documents")
