from datetime import datetime

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


class WorkspaceMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    user_id: str
    role: WorkspaceRole
    created_at: datetime
