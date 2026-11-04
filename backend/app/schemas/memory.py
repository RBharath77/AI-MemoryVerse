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
    extra_metadata: dict | None = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    category: MemoryCategory | None = None
    importance: int | None = Field(default=None, ge=1, le=10)
    is_pinned: bool | None = None
    tags: list[str] | None = None
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
    source_type: str
    source_id: str | None = None
    tags: list[str] = []
    extra_metadata: dict = {}
    created_at: datetime
    updated_at: datetime


class MemoryReviewAction(BaseModel):
    review_status: str = Field(description="approved, rejected, corrected")
    corrected_text: str | None = None
    review_notes: str | None = None
