from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(default="New Conversation", max_length=255)
    system_prompt: str | None = Field(default=None, max_length=5000)
    model: str = Field(default="gpt-4o-mini", max_length=64)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    user_id: str
    title: str
    system_prompt: str | None = None
    model: str
    temperature: float
    is_pinned: bool
    is_archived: bool
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20000, description="User prompt content")
    stream: bool = Field(default=False, description="Whether to stream response tokens")


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    workspace_id: str
    role: str
    content: str
    token_count: int = 0
    citations: list[dict] = []
    feedback: int | None = None
    extra_metadata: dict = Field(default_factory=dict)
    created_at: datetime


class ChatFeedbackRequest(BaseModel):
    rating: int = Field(ge=-1, le=1, description="1 for helpful, -1 for unhelpful")


class PromptInspectionRequest(BaseModel):
    prompt: str = Field(
        min_length=1,
        max_length=20000,
        description="Prompt text to inspect for adversarial injection",
    )


class PromptInspectionResponse(BaseModel):
    original_prompt: str
    sanitized_prompt: str
    is_safe: bool
    risk_score: float
    threat_level: str
    detected_patterns: list[str] = Field(default_factory=list)
    recommendation: str
    metadata: dict = Field(default_factory=dict)


class DebateTurn(BaseModel):
    round_number: int
    agent_role: str  # PROPONENT, SKEPTIC, ARBITRATOR
    agent_name: str
    statement: str
    evidence_citations: list[str] = Field(default_factory=list)
    timestamp: datetime


class ConsensusDebateRequest(BaseModel):
    topic: str = Field(
        min_length=3,
        max_length=1000,
        description="Debate topic, question, or proposition to deliberate",
    )
    rounds: int = Field(default=2, ge=1, le=4, description="Number of debate rounds")
    include_grounding_memories: bool = Field(default=True)


class ConsensusDebateResponse(BaseModel):
    workspace_id: str
    topic: str
    total_rounds: int
    turns: list[DebateTurn] = Field(default_factory=list)
    verdict: str  # CONSENSUS_REACHED, PARTIAL_CONSENSUS, DEADLOCK
    consensus_score: float
    final_synthesis: str
    key_conclusions: list[str] = Field(default_factory=list)
    grounding_memory_ids: list[str] = Field(default_factory=list)
    debated_at: datetime


class ClaimAttributionResult(BaseModel):
    claim_index: int
    claim_text: str
    status: str  # "SUPPORTED", "CONTRADICTED", "UNGROUNDED"
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_sources: list[str] = Field(default_factory=list)
    contradiction_detail: str | None = None


class AttributionVerificationRequest(BaseModel):
    generated_text: str = Field(
        ...,
        min_length=1,
        max_length=20000,
        description="Generated candidate text to audit for grounding fidelity and factual hallucination",
    )
    grounding_sources: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Optional explicit context chunks or memory records to verify against",
    )
    strictness: float = Field(
        default=0.75,
        ge=0.5,
        le=0.99,
        description="Strictness threshold for lexical & semantic entailment matching",
    )


class AttributionVerificationResponse(BaseModel):
    workspace_id: str
    total_claims: int
    supported_claims: int
    contradicted_claims: int
    ungrounded_claims: int
    grounding_fidelity_score: float = Field(ge=0.0, le=1.0)
    hallucination_risk_index: float = Field(ge=0.0, le=1.0)
    is_grounded: bool
    claims: list[ClaimAttributionResult] = Field(default_factory=list)
    verified_at: datetime


class UncertaintyCalibrationRequest(BaseModel):
    query: str = Field(
        ..., min_length=2, max_length=2000, description="User query or decision prompt"
    )
    candidate_response: str = Field(
        ..., min_length=2, max_length=10000, description="Assistant answer or hypothesis"
    )
    confidence_prior: float = Field(
        default=0.85, ge=0.1, le=1.0, description="Initial uncalibrated model confidence prior"
    )


class UncertaintyCalibrationResponse(BaseModel):
    workspace_id: str
    query: str
    calibrated_confidence: float = Field(ge=0.0, le=1.0)
    confidence_lower: float = Field(ge=0.0, le=1.0)
    confidence_upper: float = Field(ge=0.0, le=1.0)
    epistemic_uncertainty: float = Field(ge=0.0, le=1.0)
    aleatoric_uncertainty: float = Field(ge=0.0, le=1.0)
    evidence_entropy: float = Field(ge=0.0)
    recommendation: str  # "PROCEED", "FLAG_LOW_CONFIDENCE", "REQUIRE_HUMAN_DISAMBIGUATION"
    supporting_memory_count: int
    calibrated_at: datetime
