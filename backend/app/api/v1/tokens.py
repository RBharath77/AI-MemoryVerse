import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_workspace
from app.core.database import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.schemas.agent import (
    APITokenCreate,
    APITokenCreatedResponse,
    APITokenResponse,
)
from app.schemas.common import APIResponse
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tokens", tags=["tokens"])


async def verify_workspace_admin_or_owner(
    db: AsyncSession,
    workspace_id: str,
    user_id: str,
    is_superuser: bool,
) -> None:
    if is_superuser:
        return
    q = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id,
    )
    member = (await db.execute(q)).scalar_one_or_none()
    if not member or member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owners and administrators can create or revoke API tokens.",
        )


@router.get("", response_model=APIResponse[list[APITokenResponse]])
async def list_tokens(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[list[APITokenResponse]]:
    """List programmatic API access tokens created for this workspace."""
    tokens = await AgentService.list_api_tokens(
        db=db,
        workspace_id=current_workspace.id,
    )
    items = [
        APITokenResponse(
            id=t.id,
            name=t.name,
            token_prefix=t.token_prefix,
            scopes=t.scopes,
            last_used_at=t.last_used_at,
            expires_at=t.expires_at,
            is_revoked=t.is_revoked,
            created_at=t.created_at,
        )
        for t in tokens
    ]
    return APIResponse(success=True, data=items)


@router.post(
    "",
    response_model=APIResponse[APITokenCreatedResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_token(
    data: APITokenCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[APITokenCreatedResponse]:
    """Generate a new programmatic API token. The plaintext token is displayed ONLY once."""
    await verify_workspace_admin_or_owner(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        is_superuser=current_user.is_superuser,
    )
    token_obj, raw_secret = await AgentService.create_api_token(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        data=data,
    )
    return APIResponse(
        success=True,
        data=APITokenCreatedResponse(
            id=token_obj.id,
            name=token_obj.name,
            token_prefix=token_obj.token_prefix,
            token=raw_secret,
            scopes=token_obj.scopes,
            expires_at=token_obj.expires_at,
            created_at=token_obj.created_at,
        ),
    )


@router.delete("/{token_id}", response_model=APIResponse[dict[str, Any]])
async def revoke_token(
    token_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_workspace: Workspace = Depends(get_current_workspace),
) -> APIResponse[dict[str, Any]]:
    """Revoke an API token immediately."""
    await verify_workspace_admin_or_owner(
        db=db,
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        is_superuser=current_user.is_superuser,
    )
    await AgentService.revoke_api_token(
        db=db,
        workspace_id=current_workspace.id,
        token_id=token_id,
    )
    return APIResponse(success=True, data={"revoked": True})
