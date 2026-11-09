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
    text: str = Field(
        min_length=2,
        max_length=50000,
        description="Text content for entity and relationship extraction (max 50,000 chars)",
    )
    source_memory_id: str | None = None
    source_document_id: str | None = None


class GraphExtractionResponse(BaseModel):
    entities_created: int
    relationships_created: int
    entities: list[EntityResponse]


class PathFindingRequest(BaseModel):
    source_entity: str = Field(
        min_length=1, max_length=255, description="Source entity ID or entity name"
    )
    target_entity: str = Field(
        min_length=1, max_length=255, description="Target entity ID or entity name"
    )
    max_depth: int = Field(default=4, ge=1, le=6, description="Maximum traversal depth")


class ReasoningHop(BaseModel):
    source_name: str
    relationship: str
    target_name: str
    weight: float


class GraphReasoningPath(BaseModel):
    path_length: int
    entities: list[str]
    relationships: list[str]
    hops: list[ReasoningHop]
    path_strength: float
    explanation: str


class GraphPathReasoningResponse(BaseModel):
    workspace_id: str
    source_entity: str
    target_entity: str
    total_paths_found: int
    paths: list[GraphReasoningPath] = Field(default_factory=list)
    evaluated_at: datetime


class RelationInferenceRequest(BaseModel):
    entity_id: str | None = Field(
        default=None, description="Optional entity ID to focus hypothesis inference on"
    )
    min_confidence: float = Field(
        default=0.4, ge=0.1, le=1.0, description="Minimum confidence threshold"
    )
    limit: int = Field(default=10, ge=1, le=50)


class InferredRelationship(BaseModel):
    source_entity_id: str
    source_entity_name: str
    target_entity_id: str
    target_entity_name: str
    inferred_type: str
    confidence: float
    reasoning_chain: list[str]
    evidence_hops: list[dict[str, Any]] = Field(default_factory=list)


class RelationInferenceResponse(BaseModel):
    workspace_id: str
    total_hypotheses: int
    inferred_relationships: list[InferredRelationship] = Field(default_factory=list)
    evaluated_at: datetime


class CounterfactualSimulationRequest(BaseModel):
    scenario_text: str = Field(
        min_length=5,
        max_length=2000,
        description="Natural language scenario description, e.g. 'Replace Celery background workers with Temporal'",
    )
    target_entities: list[str] = Field(
        min_length=1,
        max_length=10,
        description="Names or IDs of primary components being modified, replaced, or deprecated",
    )
    proposed_action: str = Field(
        default="REPLACE",
        description="Action type: REPLACE, DEPRECATE, MIGRATE, REMOVE, UPGRADE",
    )
    replacement_target: str | None = Field(
        default=None,
        description="Name of the replacement component, e.g. 'Temporal'",
    )
    max_ripple_depth: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum graph hop distance for cascading ripple effect calculation",
    )


class ImpactedNode(BaseModel):
    entity_id: str
    entity_name: str
    entity_type: str
    impact_type: str  # "DIRECT" or "TRANSITIVE"
    hop_distance: int
    connected_relationships: list[str] = Field(default_factory=list)


class RiskTradeOffItem(BaseModel):
    category: str  # "architecture", "security", "performance", "operational", "data_loss"
    severity: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    description: str
    mitigation_strategy: str


class CounterfactualSimulationResponse(BaseModel):
    workspace_id: str
    scenario: str
    proposed_action: str
    target_entities: list[str] = Field(default_factory=list)
    replacement_target: str | None = None
    direct_impact_count: int
    cascading_impact_count: int
    blast_radius_score: float = Field(ge=0.0, le=1.0)
    impacted_entities: list[ImpactedNode] = Field(default_factory=list)
    risks_and_tradeoffs: list[RiskTradeOffItem] = Field(default_factory=list)
    recommended_preconditions: list[str] = Field(default_factory=list)
    simulated_at: datetime
