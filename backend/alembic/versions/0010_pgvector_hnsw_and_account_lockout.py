"""pgvector hnsw indexes and account lockout

Revision ID: 0010_hnsw_and_lockout
Revises: 0009_user_token_versioning
Create Date: 2026-11-08 17:25:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_hnsw_and_lockout"
down_revision: str | None = "0009_user_token_versioning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Add failed login attempts and lockout fields to users
    op.add_column(
        "users",
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "locked_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_mfa_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "mfa_secret",
            sa.String(length=64),
            nullable=True,
        ),
    )

    # 2. Add HNSW cosine vector indexes for PostgreSQL pgvector
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_memories_embedding_hnsw
            ON memories USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
            ON document_chunks USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
            """
        )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw;")
        op.execute("DROP INDEX IF EXISTS ix_memories_embedding_hnsw;")

    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
