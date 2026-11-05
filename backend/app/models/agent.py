import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

JSONType = JSON().with_variant(JSONB, "postgresql")


class TaskStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActionApprovalStatus(enum.StrEnum):
    APPROVED_AUTO = "approved_auto"
    PENDING_APPROVAL = "pending_approval"
    APPROVED_BY_USER = "approved_by_user"
    REJECTED_BY_USER = "rejected_by_user"


class AgentTask(Base, TimestampMixin):
    __tablename__ = "agent_tasks"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus, name="task_status_enum", native_enum=False),
        default=TaskStatus.PENDING,
        nullable=False,
        index=True,
    )
    steps_limit: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    steps_taken: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)

    actions: Mapped[list["AgentAction"]] = relationship(
        "AgentAction",
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AgentAction.created_at",
    )


class AgentAction(Base, TimestampMixin):
    __tablename__ = "agent_actions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tool_input: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    tool_output: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(16), default="low", nullable=False)
    approval_status: Mapped[ActionApprovalStatus] = mapped_column(
        SQLEnum(ActionApprovalStatus, name="action_approval_status_enum", native_enum=False),
        default=ActionApprovalStatus.APPROVED_AUTO,
        nullable=False,
        index=True,
    )
    execution_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    task: Mapped["AgentTask"] = relationship("AgentTask", back_populates="actions")


class APIToken(Base, TimestampMixin):
    __tablename__ = "api_tokens"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    scopes: Mapped[list] = mapped_column(
        JSONType,
        default=lambda: ["memories:read", "search"],
        nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
