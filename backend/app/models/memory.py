import enum
import uuid
from datetime import UTC, datetime

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


class MemoryCategory(enum.StrEnum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROJECT = "project"
    PREFERENCE = "preference"


class MemoryStatus(enum.StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class Memory(Base, TimestampMixin):
    __tablename__ = "memories"

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
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[MemoryCategory] = mapped_column(
        SQLEnum(MemoryCategory, name="memory_category_enum", native_enum=False),
        default=MemoryCategory.SEMANTIC,
        nullable=False,
        index=True,
    )
    status: Mapped[MemoryStatus] = mapped_column(
        SQLEnum(MemoryStatus, name="memory_status_enum", native_enum=False),
        default=MemoryStatus.APPROVED,
        nullable=False,
        index=True,
    )
    importance: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    superseded_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("memories.id", ondelete="SET NULL"),
        nullable=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(32),
        default="manual",
        nullable=False,
    )
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        JSONType,
        default=list,
        nullable=False,
    )
    extra_metadata: Mapped[dict] = mapped_column(
        JSONType,
        default=dict,
        nullable=False,
    )

    versions: Mapped[list["MemoryVersion"]] = relationship(
        "MemoryVersion",
        back_populates="memory",
        cascade="all, delete-orphan",
        order_by="desc(MemoryVersion.version_number)",
    )
    reviews: Mapped[list["MemoryReview"]] = relationship(
        "MemoryReview",
        back_populates="memory",
        cascade="all, delete-orphan",
    )


class MemoryVersion(Base, TimestampMixin):
    __tablename__ = "memory_versions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    memory_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    changed_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    change_reason: Mapped[str] = mapped_column(String(255), default="Update", nullable=False)

    memory: Mapped["Memory"] = relationship("Memory", back_populates="versions")


class MemoryReview(Base, TimestampMixin):
    __tablename__ = "memory_reviews"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    memory_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    review_status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
    )
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    memory: Mapped["Memory"] = relationship("Memory", back_populates="reviews")


class MemoryLink(Base, TimestampMixin):
    __tablename__ = "memory_links"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    source_memory_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_memory_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
