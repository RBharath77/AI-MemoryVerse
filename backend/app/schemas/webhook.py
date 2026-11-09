from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WebhookEndpointCreate(BaseModel):
    url: str = Field(
        min_length=8, max_length=1024, description="Destination URL for webhook event delivery"
    )
    secret: str | None = Field(
        default=None,
        max_length=128,
        description="Custom signing secret (auto-generated if omitted)",
    )
    event_types: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Event types subscribed to (e.g. ['memory.created', 'document.processed', '*'])",
    )


class WebhookEndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    url: str
    masked_secret: str
    event_types: list[str]
    is_active: bool
    created_at: datetime


class WebhookDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    endpoint_id: str
    event_type: str
    payload: dict
    status_code: int | None = None
    response_body: str | None = None
    attempt_count: int
    is_dlq: bool
    delivered_at: datetime | None = None
    created_at: datetime


class WebhookDispatchEventRequest(BaseModel):
    event_type: str = Field(
        min_length=1, max_length=64, description="Event identifier (e.g. memory.created)"
    )
    payload: dict = Field(
        default_factory=dict, description="Arbitrary JSON data payload to sign and deliver"
    )
