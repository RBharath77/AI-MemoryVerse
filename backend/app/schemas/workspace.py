from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.workspace import WorkspacePlan, WorkspaceRole


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    description: str | None = Field(default="", max_length=1000)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=128)
    description: str | None = Field(default=None, max_length=1000)
    settings: dict | None = None


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str
    owner_id: str
    plan_tier: WorkspacePlan
    settings: dict
    created_at: datetime
    updated_at: datetime


class WorkspaceMemberCreate(BaseModel):
    user_id: str
    role: WorkspaceRole = WorkspaceRole.MEMBER


class WorkspaceMemberUpdate(BaseModel):
    role: WorkspaceRole


class WorkspaceMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    user_id: str
    role: WorkspaceRole
    created_at: datetime


class WorkspaceSecretCreate(BaseModel):
    name: str = Field(
        min_length=1, max_length=64, description="Secret key identifier (e.g. OPENAI_API_KEY)"
    )
    value: str = Field(
        min_length=1, max_length=2048, description="Plaintext secret value to encrypt at rest"
    )


class WorkspaceSecretResponse(BaseModel):
    name: str
    masked_value: str
    created_at: datetime


class WorkspaceIPPolicyUpdate(BaseModel):
    ip_allowlist: list[str] = Field(
        default_factory=list,
        description="List of allowed IPv4/IPv6 CIDR network ranges (e.g. ['192.168.1.0/24'])",
    )


class WorkspaceRetentionPolicyUpdate(BaseModel):
    retention_days: int | None = Field(
        default=None,
        ge=1,
        le=3650,
        description="Maximum lifetime in days for unpinned memories before automatic archival (null for indefinite)",
    )


class WorkspaceCMEKRotateResponse(BaseModel):
    workspace_id: str
    previous_key_version: int
    new_key_version: int
    reencrypted_secrets_count: int
    rotated_at: datetime


class WorkspaceCryptoShredResponse(BaseModel):
    workspace_id: str
    shredded_secrets_count: int
    status: str
    shredded_at: datetime


class WorkspaceBenchmarkResponse(BaseModel):
    workspace_id: str
    workspace_name: str
    total_memories: int
    active_memories: int
    superseded_memories: int
    pending_conflicts: int
    resolved_conflicts: int
    conflict_resolution_rate: float
    retention_health: dict
    retrieval_performance: dict
    cache_efficiency: dict
    redundancy_rate: float
    platform_grade: str
    evaluated_at: datetime


class RAGProbeRunRequest(BaseModel):
    sample_size: int = Field(
        default=5,
        ge=1,
        le=25,
        description="Number of synthetic probes to generate and evaluate",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=25,
        description="Candidate retrieval depth for probe evaluation",
    )


class RAGProbeResult(BaseModel):
    probe_id: str
    query: str
    ground_truth_memory_id: str
    retrieved_rank: int | None = None
    hit: bool
    reciprocal_rank: float
    context_precision: float
    groundedness_score: float


class RAGBenchmarkResponse(BaseModel):
    workspace_id: str
    run_id: str
    total_probes: int
    hit_rate: float
    mean_reciprocal_rank: float
    average_precision: float
    average_groundedness: float
    overall_score: float
    letter_grade: str
    probes: list[RAGProbeResult] = Field(default_factory=list)
    evaluated_at: datetime


class RAGEvalHistoryResponse(BaseModel):
    workspace_id: str
    total_runs: int
    history: list[RAGBenchmarkResponse] = Field(default_factory=list)


class WorkspaceDLPPolicyUpdate(BaseModel):
    enabled: bool = Field(default=True, description="Whether DLP policy inspection is active")
    action: str = Field(
        default="REDACT",
        description="Enforcement action when violation detected: REDACT, BLOCK, or AUDIT",
    )
    active_rules: list[str] = Field(
        default_factory=lambda: ["CREDIT_CARD", "SSN", "API_KEY"],
        description="Standard rules enabled: CREDIT_CARD, SSN, API_KEY, EMAIL, PHONE",
    )
    custom_rules: list[dict] = Field(
        default_factory=list,
        description="List of custom regex rules: [{'name': '...', 'pattern': '...', 'replacement': '...'}]",
    )


class WorkspaceDLPPolicyResponse(BaseModel):
    workspace_id: str
    enabled: bool
    action: str
    active_rules: list[str]
    custom_rules: list[dict]
    updated_at: datetime


class WorkspaceDLPInspectRequest(BaseModel):
    text: str = Field(
        min_length=1, max_length=50000, description="Text payload to inspect against DLP policy"
    )


class WorkspaceDLPInspectResponse(BaseModel):
    original_text: str
    sanitized_text: str
    is_clean: bool
    violations: list[str] = Field(default_factory=list)
    action_taken: str
    blocked: bool


class TopicVelocity(BaseModel):
    tag: str
    baseline_freq: int
    recent_freq: int
    acceleration: float


class MemoryDriftResponse(BaseModel):
    workspace_id: str
    window_days: int
    baseline_memory_count: int
    recent_memory_count: int
    centroid_distance: float
    drift_score: float
    drift_status: str
    top_accelerating_topics: list[TopicVelocity] = Field(default_factory=list)
    top_declining_topics: list[TopicVelocity] = Field(default_factory=list)
    conflict_velocity_ratio: float
    analyzed_at: datetime


class ComplianceControlResult(BaseModel):
    control_id: str
    control_name: str
    category: str
    status: str  # PASS, WARN, FAIL
    details: str
    is_auto_remediable: bool = False


class ComplianceScorecardResponse(BaseModel):
    workspace_id: str
    compliance_score: int
    platform_grade: str
    controls_passed: int
    controls_warned: int
    controls_failed: int
    controls: list[ComplianceControlResult] = Field(default_factory=list)
    remediation_recommendations: list[str] = Field(default_factory=list)
    evaluated_at: datetime


class ComplianceRemediateResponse(BaseModel):
    workspace_id: str
    previous_score: int
    updated_score: int
    remediated_controls: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)
    remediated_at: datetime


class TimeTravelMemoryItem(BaseModel):
    id: str
    content: str
    category: str
    importance: int
    created_at: datetime
    status: str
    version_at_time: int = 1


class TimeTravelSnapshotResponse(BaseModel):
    workspace_id: str
    as_of: datetime
    active_memory_count: int
    category_breakdown: dict[str, int]
    memories: list[TimeTravelMemoryItem] = Field(default_factory=list)
    reconstructed_at: datetime


class TimelineDiffRequest(BaseModel):
    timestamp_a: datetime = Field(description="Earlier historical point in time")
    timestamp_b: datetime = Field(description="Later historical point in time")


class TimelineDiffResponse(BaseModel):
    workspace_id: str
    timestamp_a: datetime
    timestamp_b: datetime
    memories_added_count: int
    memories_superseded_count: int
    memories_modified_count: int
    net_change: int
    added_memories: list[dict[str, Any]] = Field(default_factory=list)
    superseded_memories: list[dict[str, Any]] = Field(default_factory=list)
    diff_summary: str
    analyzed_at: datetime


class CacheFreshnessResponse(BaseModel):
    workspace_id: str
    cached_entries: int
    tracked_dependencies_count: int
    avg_dependencies_per_entry: float
    hit_count: int
    miss_count: int
    hit_ratio: float
    estimated_token_savings: int
    evaluated_at: datetime


class CacheDependencyInvalidateRequest(BaseModel):
    dependency_ids: list[str] = Field(
        min_length=1,
        description="List of memory IDs or document IDs to selectively invalidate",
    )


class CacheDependencyInvalidateResponse(BaseModel):
    workspace_id: str
    invalidated_keys_count: int
    remaining_entries_count: int
    dependency_ids: list[str]
    invalidated_at: datetime


class DifferentialPrivacyMetricRequest(BaseModel):
    epsilon: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Privacy loss budget epsilon (lower value = stronger privacy, more noise)",
    )
    delta: float = Field(
        default=1e-5,
        ge=1e-8,
        le=1e-2,
        description="Differential privacy failure parameter delta",
    )
    metric_types: list[str] = Field(
        default_factory=lambda: ["tag_distribution", "category_counts", "average_importance"],
        description="Metric families to compute with differential privacy noise addition",
    )


class DifferentialPrivacyMetricResponse(BaseModel):
    workspace_id: str
    epsilon_consumed: float
    delta: float
    mechanism: str  # "Laplace", "Gaussian"
    noisy_tag_distribution: dict[str, float] = Field(default_factory=dict)
    noisy_category_counts: dict[str, float] = Field(default_factory=dict)
    noisy_average_importance: float
    total_records_analyzed: int
    privacy_guarantee: str
    evaluated_at: datetime
