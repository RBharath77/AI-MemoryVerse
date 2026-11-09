from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.memory import MemoryCategory, MemoryStatus


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000, description="Memory text content")
    category: MemoryCategory = Field(default=MemoryCategory.SEMANTIC)
    importance: int = Field(default=5, ge=1, le=10)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_pinned: bool = Field(default=False)
    tags: list[str] = Field(default_factory=list)
    source_type: str = Field(default="manual")
    source_id: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    extra_metadata: dict = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    category: MemoryCategory | None = None
    importance: int | None = Field(default=None, ge=1, le=10)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    is_pinned: bool | None = None
    tags: list[str] | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    extra_metadata: dict | None = None


class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    user_id: str
    content: str
    category: MemoryCategory
    status: MemoryStatus
    importance: int
    confidence: float
    is_pinned: bool
    valid_from: datetime
    valid_until: datetime | None = None
    superseded_by: str | None = None
    source_type: str
    source_id: str | None = None
    tags: list[str] = []
    extra_metadata: dict = {}
    created_at: datetime
    updated_at: datetime


class MemoryVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    memory_id: str
    version_number: int
    content: str
    category: str
    changed_by_user_id: str
    change_reason: str
    created_at: datetime


class MemoryReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    memory_id: str
    reviewer_user_id: str | None = None
    review_status: str
    original_text: str
    corrected_text: str | None = None
    review_notes: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    memory: MemoryResponse | None = None


class MemoryReviewAction(BaseModel):
    review_status: str = Field(description="approved, rejected, or corrected")
    corrected_text: str | None = None
    review_notes: str | None = None


class MemoryLinkCreate(BaseModel):
    target_memory_id: str
    relationship_type: str = Field(
        default="related_to"
    )  # related_to, causes, supersedes, contradicts, part_of
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class MemoryLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    source_memory_id: str
    target_memory_id: str
    relationship_type: str
    confidence: float
    created_at: datetime


class MemoryFeedbackCreate(BaseModel):
    rating: int = Field(ge=-1, le=1, description="1 for positive, -1 for negative")
    feedback_text: str | None = Field(default=None, max_length=1000)


class MemoryFeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    memory_id: str
    user_id: str
    rating: int
    feedback_text: str | None = None
    created_at: datetime


class MemoryExtractionRequest(BaseModel):
    text: str = Field(min_length=3, description="Unstructured conversational text or notes")
    source_type: str = Field(default="conversation")
    source_id: str | None = None
    auto_approve: bool = Field(
        default=False,
        description="If True and confidence is high, auto-approve directly into vault",
    )


class MemoryExtractionResponse(BaseModel):
    extracted_count: int
    approved_count: int
    pending_review_count: int
    memories: list[MemoryResponse]


class MemoryConsolidateRequest(BaseModel):
    memory_ids: list[str] = Field(
        min_length=2, description="At least two memory IDs to consolidate"
    )
    consolidated_content: str = Field(min_length=1, max_length=10000)
    category: MemoryCategory = Field(default=MemoryCategory.SEMANTIC)
    importance: int = Field(default=7, ge=1, le=10)
    tags: list[str] = Field(default_factory=list)


class MemoryImportItem(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    category: MemoryCategory = MemoryCategory.SEMANTIC
    importance: int = Field(default=5, ge=1, le=10)
    tags: list[str] = Field(default_factory=list, max_length=20)
    source_type: str = Field(default="import", max_length=64)


class MemoryImportRequest(BaseModel):
    memories: list[MemoryImportItem] = Field(min_length=1, max_length=500)


class MemoryImportResponse(BaseModel):
    imported_count: int
    duplicates_skipped: int
    total_processed: int


class MemoryAnalyticsResponse(BaseModel):
    total_memories: int
    approved_count: int
    pending_review_count: int
    superseded_count: int
    archived_count: int
    pinned_count: int
    by_category: dict[str, int]
    top_tags: list[dict[str, int | str]]


class MemoryTimelineEvent(BaseModel):
    id: str
    content: str
    category: str
    importance: int
    timestamp: datetime
    source_type: str
    status: str


class MemoryTimelineResponse(BaseModel):
    events: list[MemoryTimelineEvent]
    total: int


class MemoryDeduplicationRequest(BaseModel):
    similarity_threshold: float = Field(
        default=0.90,
        ge=0.70,
        le=1.0,
        description="Cosine similarity threshold above which memories are considered redundant",
    )
    auto_merge: bool = Field(
        default=True,
        description="Whether to automatically consolidate duplicate memories into primary records",
    )


class MemoryDeduplicationResponse(BaseModel):
    scanned_count: int
    duplicates_found: int
    consolidated_count: int
    details: list[dict] = Field(default_factory=list)


class MemoryReinforceResponse(BaseModel):
    id: str
    workspace_id: str
    retention_strength: float
    stability_days: float
    access_count: int
    last_reinforced_at: datetime


class MemoryDecayAnalyticsResponse(BaseModel):
    total_memories: int
    strong_count: int
    fading_count: int
    dormant_count: int
    average_retention: float
    dormant_memory_ids: list[str] = Field(default_factory=list)


class WorkspaceIntegrityVerifyResponse(BaseModel):
    total_checked: int
    valid_count: int
    tampered_count: int
    tampered_ids: list[str] = Field(default_factory=list)
    is_compromised: bool
    verified_at: datetime


class MemoryConflictResolutionRequest(BaseModel):
    strategy: str = Field(
        ...,
        description="Resolution strategy: 'supersede', 'merge', 'keep_both', or 'discard'",
    )
    merged_content: str | None = Field(
        default=None,
        description="Consolidated text required when strategy is 'merge'",
    )
    notes: str | None = Field(
        default=None,
        description="Optional justification note for audit log",
    )


class SemanticFactDiffResponse(BaseModel):
    old_content: str
    new_content: str
    similarity_score: float
    added_tokens: list[str] = Field(default_factory=list)
    removed_tokens: list[str] = Field(default_factory=list)
    contradicted_entities: list[str] = Field(default_factory=list)
    temporal_shift_summary: str = ""


class MemoryConflictResolutionResponse(BaseModel):
    resolved_memory_id: str
    previous_memory_id: str | None = None
    strategy: str
    status: str
    fact_diff: SemanticFactDiffResponse
    resolved_at: datetime


class MemoryAutoConsolidateRequest(BaseModel):
    topic: str | None = Field(
        default=None,
        description="Optional specific topic/tag filter to target for consolidation",
    )
    min_memories: int = Field(
        default=2,
        ge=2,
        le=50,
        description="Minimum number of memories required to form a consolidation cluster",
    )
    dry_run: bool = Field(
        default=True,
        description="Whether to preview candidate clusters without persisting changes",
    )
    target_category: MemoryCategory = Field(
        default=MemoryCategory.SEMANTIC,
        description="Category to assign to newly synthesized memories",
    )


class ConsolidationCluster(BaseModel):
    topic: str
    source_memory_ids: list[str]
    synthesized_content: str
    confidence: float
    compression_ratio: float
    source_categories: list[str] = Field(default_factory=list)


class MemoryAutoConsolidateResponse(BaseModel):
    clusters: list[ConsolidationCluster] = Field(default_factory=list)
    total_source_memories: int
    consolidated_memories_created: int
    new_memory_ids: list[str] = Field(default_factory=list)
    dry_run: bool
    consolidated_at: datetime


class AssociativeNode(BaseModel):
    node_id: str
    node_type: str
    content: str
    activation_energy: float
    hop_distance: int
    relationship_path: list[str] = Field(default_factory=list)


class MemoryAssociationsResponse(BaseModel):
    seed_memory_id: str
    seed_content: str
    total_activated_nodes: int
    associations: list[AssociativeNode] = Field(default_factory=list)
    max_activation: float
    explored_at: datetime


class ReflectionInsightItem(BaseModel):
    id: str
    title: str
    insight_type: str  # "preference", "habit", "architecture", "decision", "heuristic", "goal"
    statement: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_memory_ids: list[str] = Field(default_factory=list)
    suggested_action: str | None = None
    tags: list[str] = Field(default_factory=list)


class MemoryReflectionRequest(BaseModel):
    focus_area: str | None = Field(
        default=None,
        description="Optional thematic focus area, e.g. 'architecture', 'coding_standards', 'preferences'",
    )
    lookback_days: int = Field(
        default=30, ge=1, le=365, description="Lookback window in days to gather episodic memories"
    )
    max_memories: int = Field(
        default=50, ge=2, le=200, description="Maximum number of active memories to reflect over"
    )
    auto_commit: bool = Field(
        default=False,
        description="Persist newly synthesized reflections as permanent semantic memories",
    )


class MemoryReflectionResponse(BaseModel):
    workspace_id: str
    total_memories_analyzed: int
    total_reflections_generated: int
    insights: list[ReflectionInsightItem] = Field(default_factory=list)
    committed_memory_ids: list[str] = Field(default_factory=list)
    auto_committed: bool
    reflected_at: datetime


class ExistingReflectionsResponse(BaseModel):
    workspace_id: str
    total_reflections: int
    reflections: list[MemoryResponse] = Field(default_factory=list)


class SleepCycleSimulationRequest(BaseModel):
    utility_threshold: float = Field(
        default=0.35,
        ge=0.05,
        le=0.90,
        description="Utility threshold below which a memory is considered candidate for sleep-cycle pruning",
    )
    inactivity_days: int = Field(
        default=14,
        ge=1,
        le=365,
        description="Minimum days without access or modification before eligible for pruning",
    )
    protect_pinned: bool = Field(
        default=True,
        description="Protect all pinned memories from ever being pruned",
    )
    protect_graph_connected: bool = Field(
        default=True,
        description="Protect memories that have active graph entity or relationship anchors",
    )
    max_candidates: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum candidates to identify in a single simulation pass",
    )


class PrunableCandidate(BaseModel):
    memory_id: str
    content_snippet: str
    importance: int
    calculated_utility: float
    inactivity_days: int
    reason: str


class SleepCycleSimulationResponse(BaseModel):
    workspace_id: str
    total_active_memories: int
    candidates_identified: int
    estimated_token_savings: int
    protected_count: int
    candidates: list[PrunableCandidate] = Field(default_factory=list)
    simulated_at: datetime


class SleepCycleExecutionRequest(BaseModel):
    candidate_memory_ids: list[str] = Field(
        min_length=1,
        max_length=500,
        description="List of memory IDs to process in sleep cycle",
    )
    action: str = Field(
        default="ARCHIVE",
        description="'ARCHIVE' (sets status ARCHIVED), 'SUPERSEDE' (sets status SUPERSEDED), or 'COMPACT' (creates single consolidated digest)",
    )
    compaction_title: str | None = Field(
        default=None,
        description="Optional title for the consolidated digest memory when action is 'COMPACT'",
    )


class SleepCycleExecutionResponse(BaseModel):
    workspace_id: str
    action_executed: str
    processed_count: int
    compacted_memory_id: str | None = None
    executed_at: datetime


class MemoryAclUpdate(BaseModel):
    visibility: str = Field(
        default="workspace",
        pattern=r"^(workspace|restricted|private)$",
        description="'workspace' (all members), 'restricted' (role/user list), 'private' (author only)",
    )
    allowed_roles: list[str] = Field(
        default_factory=list,
        description="Allowed workspace roles when visibility is 'restricted' (e.g. ['owner', 'admin'])",
    )
    allowed_user_ids: list[str] = Field(
        default_factory=list,
        description="Explicit user IDs permitted to access when visibility is 'restricted'",
    )


class MemoryAclResponse(BaseModel):
    memory_id: str
    visibility: str
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_user_ids: list[str] = Field(default_factory=list)
    can_read: bool
    can_write: bool
    updated_at: datetime


class HierarchyNode(BaseModel):
    node_id: str
    level: int = Field(
        ge=0,
        le=4,
        description="0=Leaf/Episodic, 1=Tactical Cluster, 2=Core Principle, 3=Root Axiom",
    )
    title: str
    content_summary: str
    category: str
    memory_ids: list[str] = Field(default_factory=list)
    parent_node_id: str | None = None
    child_node_ids: list[str] = Field(default_factory=list)
    abstraction_depth: int = 0


class MemoryHierarchyBuildRequest(BaseModel):
    max_levels: int = Field(default=3, ge=2, le=4, description="Max depth of abstraction pyramid")
    category_filter: str | None = Field(
        default=None, description="Optional category filter (e.g. project, semantic)"
    )
    rebuild: bool = Field(
        default=False, description="Force re-clustering and abstraction recomputation"
    )


class MemoryHierarchyResponse(BaseModel):
    workspace_id: str
    total_memories_indexed: int
    total_nodes: int
    max_depth: int
    compression_ratio: float = Field(ge=0.0)
    nodes: list[HierarchyNode] = Field(default_factory=list)
    root_node_ids: list[str] = Field(default_factory=list)
    built_at: datetime


class HierarchyDrilldownRequest(BaseModel):
    node_id: str = Field(
        ..., min_length=1, description="Hierarchy node ID to inspect and drill down"
    )


class HierarchyDrilldownResponse(BaseModel):
    workspace_id: str
    node: HierarchyNode
    ancestor_chain: list[HierarchyNode] = Field(default_factory=list)
    descendant_nodes: list[HierarchyNode] = Field(default_factory=list)
    underlying_memories: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_at: datetime


class MemoryReviewCard(BaseModel):
    memory_id: str
    content_snippet: str
    category: str
    repetition_number: int
    ease_factor: float
    interval_days: int
    retention_probability: float
    last_reviewed_at: datetime | None = None
    next_review_due: datetime
    is_overdue: bool


class SpacedRepetitionScheduleResponse(BaseModel):
    workspace_id: str
    total_cards: int
    due_now_count: int
    upcoming_count: int
    average_retention_probability: float
    cards: list[MemoryReviewCard] = Field(default_factory=list)
    generated_at: datetime


class SpacedRepetitionReviewSubmit(BaseModel):
    memory_id: str
    rating: int = Field(
        ge=0,
        le=5,
        description="SM-2 recall rating: 0=blackout, 3=correct with difficulty, 5=perfect recall",
    )


class SpacedRepetitionReviewResponse(BaseModel):
    workspace_id: str
    memory_id: str
    previous_repetition: int
    new_repetition: int
    previous_ease_factor: float
    new_ease_factor: float
    new_interval_days: int
    next_review_due: datetime
    reviewed_at: datetime


class TimeLockedMemoryCreate(BaseModel):
    secret_content: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        description="Sensitive plaintext to encrypt in time-locked enclave",
    )
    ttl_seconds: int = Field(
        default=3600, ge=60, le=2592000, description="Time to live before irreversible destruction"
    )
    max_views: int = Field(
        default=1, ge=1, le=10, description="Max allowed reads before auto burn-on-read"
    )
    unlock_delay_seconds: int = Field(
        default=0,
        ge=0,
        le=86400,
        description="Optional delay before the secret can first be unlocked",
    )
    hint: str | None = Field(
        default=None, max_length=200, description="Non-sensitive public hint or label"
    )


class TimeLockedMemoryResponse(BaseModel):
    vault_id: str
    workspace_id: str
    hint: str | None = None
    max_views: int
    views_remaining: int
    unlock_at: datetime
    expires_at: datetime
    is_unlocked: bool
    is_burned: bool
    created_at: datetime


class TimeLockedMemoryRevealResponse(BaseModel):
    vault_id: str
    workspace_id: str
    decrypted_content: str
    views_remaining: int
    is_burned: bool
    expires_at: datetime
    revealed_at: datetime
