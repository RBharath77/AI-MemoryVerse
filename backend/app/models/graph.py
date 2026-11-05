import enum
import uuid

from sqlalchemy import (
    JSON,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

JSONType = JSON().with_variant(JSONB, "postgresql")


class EntityType(enum.StrEnum):
    PERSON = "person"
    ORGANIZATION = "organization"
    TECHNOLOGY = "technology"
    PROJECT = "project"
    CONCEPT = "concept"
    LOCATION = "location"
    EVENT = "event"


class GraphEntity(Base, TimestampMixin):
    __tablename__ = "graph_entities"

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
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[EntityType] = mapped_column(
        SQLEnum(EntityType, name="entity_type_enum", native_enum=False),
        default=EntityType.CONCEPT,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mention_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)

    outgoing_relationships: Mapped[list["GraphRelationship"]] = relationship(
        "GraphRelationship",
        foreign_keys="GraphRelationship.source_entity_id",
        back_populates="source_entity",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    incoming_relationships: Mapped[list["GraphRelationship"]] = relationship(
        "GraphRelationship",
        foreign_keys="GraphRelationship.target_entity_id",
        back_populates="target_entity",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "name",
            "entity_type",
            name="uq_workspace_entity_name_type",
        ),
    )


class GraphRelationship(Base, TimestampMixin):
    __tablename__ = "graph_relationships"

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
    source_entity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("graph_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_entity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("graph_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    source_memory_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("memories.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    extra_metadata: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)

    source_entity: Mapped["GraphEntity"] = relationship(
        "GraphEntity",
        foreign_keys=[source_entity_id],
        back_populates="outgoing_relationships",
        lazy="selectin",
    )
    target_entity: Mapped["GraphEntity"] = relationship(
        "GraphEntity",
        foreign_keys=[target_entity_id],
        back_populates="incoming_relationships",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "source_entity_id",
            "target_entity_id",
            "relationship_type",
            name="uq_workspace_relationship_edge",
        ),
    )
