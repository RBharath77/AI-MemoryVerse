import enum
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin

JSONType = JSON().with_variant(JSONB, "postgresql")


class ReportType(enum.StrEnum):
    DAILY_DIGEST = "daily_digest"
    WEEKLY_SUMMARY = "weekly_summary"
    TOPIC_RESEARCH = "topic_research"
    PROJECT_BRIEF = "project_brief"


class ReportStatus(enum.StrEnum):
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class InsightType(enum.StrEnum):
    STALE_KNOWLEDGE = "stale_knowledge"
    CONTRADICTION_ALERT = "contradiction_alert"
    KNOWLEDGE_GAP = "knowledge_gap"
    TRENDING_TOPIC = "trending_topic"
    CONSOLIDATION_OPPORTUNITY = "consolidation_opportunity"


class ResearchReport(Base, TimestampMixin):
    __tablename__ = "research_reports"

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
    topic: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    report_type: Mapped[ReportType] = mapped_column(
        SQLEnum(ReportType, name="report_type_enum", native_enum=False),
        default=ReportType.TOPIC_RESEARCH,
        nullable=False,
        index=True,
    )
    status: Mapped[ReportStatus] = mapped_column(
        SQLEnum(ReportStatus, name="report_status_enum", native_enum=False),
        default=ReportStatus.COMPLETED,
        nullable=False,
    )
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    key_findings: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    action_items: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    sources_used: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)


class KnowledgeInsight(Base, TimestampMixin):
    __tablename__ = "knowledge_insights"

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
    insight_type: Mapped[InsightType] = mapped_column(
        SQLEnum(InsightType, name="insight_type_enum", native_enum=False),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_action: Mapped[str] = mapped_column(String(500), nullable=False)
    related_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    related_memory_ids: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    is_dismissed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    extra_metadata: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
