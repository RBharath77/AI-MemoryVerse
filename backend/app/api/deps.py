from fastapi import Cookie, Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember

# Security scheme for Swagger UI
security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    auth_header: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
) -> User:
    token: str | None = None
    if auth_header and auth_header.credentials:
        token = auth_header.credentials
    elif access_token_cookie:
        token = access_token_cookie

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token claims.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    query = (
        select(User)
        .options(
            selectinload(User.profile),
            selectinload(User.workspace_memberships),
        )
        .where(User.id == user_id)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


async def get_current_workspace(
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """Resolve the active workspace for the current request.
    If X-Workspace-ID is provided, verify membership.
    Otherwise, fall back to the user's first available workspace.
    """
    workspace_id = x_workspace_id
    if not workspace_id:
        if not current_user.workspace_memberships:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User does not belong to any workspace.",
            )
        workspace_id = current_user.workspace_memberships[0].workspace_id

    # Verify membership in database
    query = (
        select(Workspace)
        .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
        .where(
            Workspace.id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
    )
    result = await db.execute(query)
    workspace = result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to the requested workspace is denied or workspace does not exist.",
        )

    return workspace
