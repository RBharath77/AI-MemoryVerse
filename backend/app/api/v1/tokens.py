import logging
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_workspace
from app.core.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.agent import (
    APITokenCreate,
    APITokenCreatedResponse,
    APITokenResponse,
)
from app.schemas.common import APIResponse
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tokens", tags=["tokens"])


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
    await AgentService.revoke_api_token(
        db=db,
        workspace_id=current_workspace.id,
        token_id=token_id,
    )
    return APIResponse(success=True, data={"revoked": True})
