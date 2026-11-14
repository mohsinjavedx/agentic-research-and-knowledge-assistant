"""Enable pgvector; domain tables arrive with their implementation phases."""

from alembic import op

revision = "0001_pgvector"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # The extension may be shared by other schemas. Never drop it automatically.
    pass
