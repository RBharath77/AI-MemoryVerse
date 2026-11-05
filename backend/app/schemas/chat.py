from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(default="New Conversation", max_length=255)
    system_prompt: str | None = None
    model: str = Field(default="gpt-4o-mini")
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
    created_at: datetime


class ChatFeedbackRequest(BaseModel):
    rating: int = Field(ge=-1, le=1, description="1 for helpful, -1 for unhelpful")
