from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentTaskCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    goal: str = Field(..., min_length=5, max_length=5000)
    steps_limit: int = Field(default=10, ge=1, le=25)


class AgentActionResponse(BaseModel):
    id: str
    task_id: str
    tool_name: str
    tool_input: dict[str, Any] = Field(default_factory=dict)
    tool_output: dict[str, Any] | None = None
    risk_level: str
    approval_status: str
    execution_latency_ms: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentTaskResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    title: str
    goal: str
    status: str
    steps_limit: int
    steps_taken: int
    result_summary: str | None = None
    error_message: str | None = None
    actions: list[AgentActionResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentTaskListResponse(BaseModel):
    items: list[AgentTaskResponse]
    total: int


class URLImportRequest(BaseModel):
    url: str = Field(..., min_length=7, max_length=2000)
    ingest_as_document: bool = False


class URLImportResponse(BaseModel):
    url: str
    title: str
    content: str
    word_count: int
    document_id: str | None = None


class APITokenCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    scopes: list[str] = Field(default_factory=lambda: ["memories:read", "search"])
    expires_in_days: int | None = Field(default=90, ge=1, le=365)


class APITokenCreatedResponse(BaseModel):
    id: str
    name: str
    token_prefix: str
    token: str  # Plaintext key returned strictly once
    scopes: list[str]
    expires_at: datetime | None
    created_at: datetime


class APITokenResponse(BaseModel):
    id: str
    name: str
    token_prefix: str
    scopes: list[str]
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    is_revoked: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IntentRuleViolation(BaseModel):
    rule_name: str
    severity: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    description: str
    matched_pattern: str | None = None


class IntentInspectionRequest(BaseModel):
    prompt: str = Field(
        ..., min_length=1, max_length=10000, description="Agent prompt or directive to evaluate"
    )
    tool_name: str | None = Field(
        default=None, description="Optional target tool name planned for invocation"
    )
    tool_args: dict[str, Any] = Field(default_factory=dict, description="Target tool parameters")
    mode: str = Field(
        default="ENFORCE",
        pattern=r"^(ENFORCE|AUDIT)$",
        description="'ENFORCE' blocks execution, 'AUDIT' logs warnings",
    )
    risk_threshold: float = Field(
        default=0.60,
        ge=0.1,
        le=0.99,
        description="Risk score threshold above which intent is blocked",
    )


class IntentInspectionResponse(BaseModel):
    workspace_id: str
    safety_class: str  # "BENIGN", "SUSPICIOUS", "EXFILTRATION_ATTEMPT", "PRIVILEGE_ESCALATION", "DESTRUCTIVE_MUTATION"
    risk_score: float = Field(ge=0.0, le=1.0)
    is_allowed: bool
    violations: list[IntentRuleViolation] = Field(default_factory=list)
    mitigation_action: str  # "ALLOW", "QUARANTINE_BLOCKED", "LOGGED_AUDIT_WARNING"
    inspected_at: datetime
