from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HybridSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=10, ge=1, le=50)
    include_documents: bool = True
    include_memories: bool = True
    filter_category: str | None = None


class SearchResultResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_type: str
    id: str
    title: str
    content: str
    score: float
    category: str | None = None
    section_title: str | None = None
    metadata: dict = {}


class HybridSearchResponse(BaseModel):
    query: str
    results: list[SearchResultResponseItem]
    total_found: int


class FederatedSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    workspace_ids: list[str] = Field(
        min_length=1,
        max_length=10,
        description="List of workspace IDs to federate retrieval across",
    )
    top_k_per_workspace: int = Field(default=5, ge=1, le=20)
    include_documents: bool = Field(default=True)
    include_memories: bool = Field(default=True)


class FederatedSearchResultItem(BaseModel):
    source_workspace_id: str
    source_workspace_name: str
    source_type: str  # memory or document
    id: str
    title: str
    content: str
    score: float
    category: str | None = None
    metadata: dict = Field(default_factory=dict)


class FederatedSearchResponse(BaseModel):
    query: str
    total_results: int
    federated_workspaces_searched: list[str] = Field(default_factory=list)
    results: list[FederatedSearchResultItem] = Field(default_factory=list)
    searched_at: datetime


class SubQueryItem(BaseModel):
    sub_query_id: str
    sub_query: str
    aspect: str
    priority: int = 1


class SubQueryExecutionResult(BaseModel):
    sub_query_id: str
    sub_query: str
    aspect: str
    matches_found: int
    results: list[SearchResultResponseItem] = Field(default_factory=list)


class DecomposedSearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    max_sub_queries: int = Field(default=4, ge=1, le=8)
    top_k_per_sub_query: int = Field(default=5, ge=1, le=20)
    include_documents: bool = Field(default=True)
    include_memories: bool = Field(default=True)


class DecomposedSearchResponse(BaseModel):
    original_query: str
    sub_queries: list[SubQueryItem] = Field(default_factory=list)
    sub_query_executions: list[SubQueryExecutionResult] = Field(default_factory=list)
    fused_results: list[SearchResultResponseItem] = Field(default_factory=list)
    synthesis_briefing: str
    total_unique_sources: int
    executed_at: datetime


class ModalScoreBreakdown(BaseModel):
    text_score: float = Field(ge=0.0, le=1.0)
    code_score: float = Field(ge=0.0, le=1.0)
    tabular_score: float = Field(ge=0.0, le=1.0)
    audio_score: float = Field(ge=0.0, le=1.0)


class FusedMemoryResult(BaseModel):
    memory_id: str
    content: str
    category: str
    primary_modality: str  # "text", "code", "table", "audio"
    fused_score: float = Field(ge=0.0, le=1.0)
    modal_scores: ModalScoreBreakdown
    modality_badges: list[str] = Field(default_factory=list)
    matched_aspects: list[str] = Field(default_factory=list)


class CrossModalSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000)
    preferred_modalities: list[str] = Field(
        default_factory=lambda: ["text", "code", "table", "audio"]
    )
    text_weight: float = Field(default=0.40, ge=0.0, le=1.0)
    code_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    table_weight: float = Field(default=0.20, ge=0.0, le=1.0)
    audio_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    top_k: int = Field(default=10, ge=1, le=50)


class CrossModalFusionResponse(BaseModel):
    workspace_id: str
    query: str
    total_candidates_evaluated: int
    cross_modal_alignment_score: float = Field(ge=0.0, le=1.0)
    modality_distribution: dict[str, int] = Field(default_factory=dict)
    results: list[FusedMemoryResult] = Field(default_factory=list)
    executed_at: datetime
