"""knowledge graph tables

Revision ID: 0005_knowledge_graph
Revises: 0004_rag_chat
Create Date: 2026-11-05 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_knowledge_graph"
down_revision: str | None = "0004_rag_chat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. graph_entities
    op.create_table(
        "graph_entities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(length=36),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False, server_default="concept"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "extra_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "workspace_id", "name", "entity_type", name="uq_workspace_entity_name_type"
        ),
    )
    op.create_index(op.f("ix_graph_entities_workspace_id"), "graph_entities", ["workspace_id"])
    op.create_index(op.f("ix_graph_entities_name"), "graph_entities", ["name"])
    op.create_index(op.f("ix_graph_entities_entity_type"), "graph_entities", ["entity_type"])

    # 2. graph_relationships
    op.create_table(
        "graph_relationships",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(length=36),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_entity_id",
            sa.String(length=36),
            sa.ForeignKey("graph_entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_entity_id",
            sa.String(length=36),
            sa.ForeignKey("graph_entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relationship_type", sa.String(length=64), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "source_memory_id",
            sa.String(length=36),
            sa.ForeignKey("memories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "extra_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "workspace_id",
            "source_entity_id",
            "target_entity_id",
            "relationship_type",
            name="uq_workspace_relationship_edge",
        ),
    )
    op.create_index(
        op.f("ix_graph_relationships_workspace_id"), "graph_relationships", ["workspace_id"]
    )
    op.create_index(
        op.f("ix_graph_relationships_source_entity_id"), "graph_relationships", ["source_entity_id"]
    )
    op.create_index(
        op.f("ix_graph_relationships_target_entity_id"), "graph_relationships", ["target_entity_id"]
    )
    op.create_index(
        op.f("ix_graph_relationships_relationship_type"),
        "graph_relationships",
        ["relationship_type"],
    )


def downgrade() -> None:
    op.drop_table("graph_relationships")
    op.drop_table("graph_entities")
