"""agents and integrations tables

Revision ID: 0007_agents_and_integrations
Revises: 0006_research_and_insights
Create Date: 2026-11-05 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_agents_and_integrations"
down_revision: str | None = "0006_research_and_insights"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. agent_tasks
    op.create_table(
        "agent_tasks",
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
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("steps_limit", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("steps_taken", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "extra_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_agent_tasks_workspace_id"), "agent_tasks", ["workspace_id"])
    op.create_index(op.f("ix_agent_tasks_user_id"), "agent_tasks", ["user_id"])
    op.create_index(op.f("ix_agent_tasks_status"), "agent_tasks", ["status"])

    # 2. agent_actions
    op.create_table(
        "agent_actions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(length=36),
            sa.ForeignKey("agent_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.String(length=36),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column(
            "tool_input",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "tool_output",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="low"),
        sa.Column(
            "approval_status", sa.String(length=32), nullable=False, server_default="approved_auto"
        ),
        sa.Column("execution_latency_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_agent_actions_task_id"), "agent_actions", ["task_id"])
    op.create_index(op.f("ix_agent_actions_workspace_id"), "agent_actions", ["workspace_id"])
    op.create_index(op.f("ix_agent_actions_tool_name"), "agent_actions", ["tool_name"])
    op.create_index(op.f("ix_agent_actions_approval_status"), "agent_actions", ["approval_status"])

    # 3. api_tokens
    op.create_table(
        "api_tokens",
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
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("token_hash", sa.String(length=64), unique=True, nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column(
            "scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_api_tokens_workspace_id"), "api_tokens", ["workspace_id"])
    op.create_index(op.f("ix_api_tokens_token_hash"), "api_tokens", ["token_hash"])
    op.create_index(op.f("ix_api_tokens_is_revoked"), "api_tokens", ["is_revoked"])


def downgrade() -> None:
    op.drop_table("api_tokens")
    op.drop_table("agent_actions")
    op.drop_table("agent_tasks")
