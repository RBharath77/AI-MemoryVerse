from datetime import datetime

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
    content: str
    category: MemoryCategory = MemoryCategory.SEMANTIC
    importance: int = 5
    tags: list[str] = []
    source_type: str = "import"


class MemoryImportRequest(BaseModel):
    memories: list[MemoryImportItem] = Field(min_length=1)


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
