from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.research import ReportType


class ReportGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=200)
    report_type: ReportType = ReportType.TOPIC_RESEARCH
    focus_areas: list[str] = Field(default_factory=list)
    days_back: int = Field(default=30, ge=1, le=365)


class ReportResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    title: str
    topic: str
    report_type: str
    status: str
    content_markdown: str
    key_findings: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    sources_used: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportListResponse(BaseModel):
    items: list[ReportResponse]
    total: int


class InsightResponse(BaseModel):
    id: str
    workspace_id: str
    insight_type: str
    title: str
    description: str
    suggested_action: str
    related_entity_id: str | None = None
    related_memory_ids: list[str] = Field(default_factory=list)
    is_dismissed: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InsightListResponse(BaseModel):
    items: list[InsightResponse]
    total: int


class VoiceChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None
    voice: str = "alloy"


class VoiceChatResponse(BaseModel):
    user_query: str
    assistant_response: str
    conversation_id: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    audio_base64: str | None = None
    audio_mime_type: str = "audio/wav"
