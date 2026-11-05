import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.workspace import WorkspacePlan

if TYPE_CHECKING:
    from app.models.workspace import Workspace

JSONType = JSON().with_variant(JSONB, "postgresql")


class SubscriptionStatus(enum.StrEnum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    plan_tier: Mapped[WorkspacePlan] = mapped_column(
        SQLEnum(WorkspacePlan, name="workspace_plan_enum", native_enum=False),
        default=WorkspacePlan.FREE,
        nullable=False,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SQLEnum(SubscriptionStatus, name="subscription_status_enum", native_enum=False),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

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
    invoice_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="paid", nullable=False)
    invoice_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    workspace_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
