"""research reports and knowledge insights tables

Revision ID: 0006_research_and_insights
Revises: 0005_knowledge_graph
Create Date: 2026-11-05 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006_research_and_insights"
down_revision: Union[str, None] = "0005_knowledge_graph"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. research_reports
    op.create_table(
        "research_reports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(length=36),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("report_type", sa.String(length=32), nullable=False, server_default="topic_research"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column(
            "key_findings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "action_items",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "sources_used",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "extra_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_research_reports_workspace_id"), "research_reports", ["workspace_id"])
    op.create_index(op.f("ix_research_reports_user_id"), "research_reports", ["user_id"])
    op.create_index(op.f("ix_research_reports_topic"), "research_reports", ["topic"])
    op.create_index(op.f("ix_research_reports_report_type"), "research_reports", ["report_type"])

    # 2. knowledge_insights
    op.create_table(
        "knowledge_insights",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(length=36),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("insight_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("suggested_action", sa.String(length=500), nullable=False),
        sa.Column("related_entity_id", sa.String(length=36), nullable=True),
        sa.Column(
            "related_memory_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("is_dismissed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "extra_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_knowledge_insights_workspace_id"), "knowledge_insights", ["workspace_id"])
    op.create_index(op.f("ix_knowledge_insights_insight_type"), "knowledge_insights", ["insight_type"])
    op.create_index(op.f("ix_knowledge_insights_is_dismissed"), "knowledge_insights", ["is_dismissed"])


def downgrade() -> None:
    op.drop_table("knowledge_insights")
    op.drop_table("research_reports")
