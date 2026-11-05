from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.graph import EntityType


class EntityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    entity_type: EntityType = Field(default=EntityType.CONCEPT)
    description: str | None = Field(default=None, max_length=5000)
    extra_metadata: dict[str, Any] = Field(default_factory=dict)


class EntityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    entity_type: EntityType | None = None
    description: str | None = None
    extra_metadata: dict[str, Any] | None = None


class EntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    name: str
    entity_type: EntityType
    description: str | None = None
    mention_count: int = 1
    degree: int = 0
    extra_metadata: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime


class RelationshipCreate(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relationship_type: str = Field(min_length=1, max_length=64, default="relates_to")
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
    source_memory_id: str | None = None
    source_document_id: str | None = None
    extra_metadata: dict[str, Any] = Field(default_factory=dict)


class RelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    source_entity_id: str
    target_entity_id: str
    source_entity_name: str | None = None
    target_entity_name: str | None = None
    relationship_type: str
    weight: float
    source_memory_id: str | None = None
    source_document_id: str | None = None
    created_at: datetime


class GraphNode(BaseModel):
    id: str
    name: str
    entity_type: str
    mention_count: int
    degree: int


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship_type: str
    weight: float


class GraphDataResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    total_nodes: int
    total_edges: int


class GraphAnalyticsResponse(BaseModel):
    total_entities: int
    total_relationships: int
    entity_type_breakdown: dict[str, int]
    top_central_entities: list[dict[str, Any]]
    average_degree: float


class GraphExtractionRequest(BaseModel):
    text: str = Field(min_length=2)
    source_memory_id: str | None = None
    source_document_id: str | None = None


class GraphExtractionResponse(BaseModel):
    entities_created: int
    relationships_created: int
    entities: list[EntityResponse]
