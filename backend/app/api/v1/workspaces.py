from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.get("", response_model=APIResponse[list[WorkspaceResponse]])
async def list_workspaces(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    workspaces = await WorkspaceService.get_user_workspaces(db, current_user.id)
    return APIResponse(
        success=True,
        data=[WorkspaceResponse.model_validate(w) for w in workspaces],
    )


@router.post("", response_model=APIResponse[WorkspaceResponse], status_code=status.HTTP_201_CREATED)
async def create_workspace(
    data: WorkspaceCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await WorkspaceService.create_workspace(db, current_user, data)
    return APIResponse(
        success=True,
        data=WorkspaceResponse.model_validate(workspace),
    )


@router.get("/{workspace_id}", response_model=APIResponse[WorkspaceResponse])
async def get_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, current_user.id)
    return APIResponse(
        success=True,
        data=WorkspaceResponse.model_validate(workspace),
    )


@router.patch("/{workspace_id}", response_model=APIResponse[WorkspaceResponse])
async def update_workspace(
    workspace_id: str,
    data: WorkspaceUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await WorkspaceService.update_workspace(db, workspace_id, current_user.id, data)
    return APIResponse(
        success=True,
        data=WorkspaceResponse.model_validate(workspace),
    )


@router.get("/{workspace_id}/members", response_model=APIResponse[list[WorkspaceMemberResponse]])
async def list_workspace_members(
    workspace_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    members = await WorkspaceService.get_workspace_members(db, workspace_id, current_user.id)
    return APIResponse(
        success=True,
        data=[WorkspaceMemberResponse.model_validate(m) for m in members],
    )


@router.post(
    "/{workspace_id}/members",
    response_model=APIResponse[WorkspaceMemberResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_workspace_member(
    workspace_id: str,
    data: WorkspaceMemberCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    member = await WorkspaceService.add_workspace_member(db, workspace_id, current_user.id, data)
    return APIResponse(
        success=True,
        data=WorkspaceMemberResponse.model_validate(member),
    )


@router.delete("/{workspace_id}/members/{user_id}", response_model=APIResponse[dict])
async def remove_workspace_member(
    workspace_id: str,
    user_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await WorkspaceService.remove_workspace_member(db, workspace_id, current_user.id, user_id)
    return APIResponse(
        success=True,
        data={"message": "Member removed successfully."},
    )
