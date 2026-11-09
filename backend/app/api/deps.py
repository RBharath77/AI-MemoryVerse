from datetime import UTC, datetime

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import decode_token, hash_token
from app.models.agent import APIToken
from app.models.user import User, UserSession
from app.models.workspace import Workspace, WorkspaceMember

# Security scheme for Swagger UI
security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request = None,
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

    user_id: str | None = None
    if token.startswith("mv_live_"):
        token_h = hash_token(token)
        query_token = select(APIToken).where(
            APIToken.token_hash == token_h,
            APIToken.is_revoked.is_(False),
        )
        token_record = (await db.execute(query_token)).scalar_one_or_none()
        is_expired = False
        if token_record and token_record.expires_at:
            if token_record.expires_at.tzinfo is None:
                is_expired = token_record.expires_at < datetime.utcnow()
            else:
                is_expired = token_record.expires_at < datetime.now(UTC)

        if not token_record or is_expired:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired programmatic API token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = token_record.user_id
        token_record.last_used_at = datetime.now(UTC)
        if request is not None:
            request.state.api_token_scopes = token_record.scopes
        await db.commit()
    else:
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = payload.get("sub")
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

    # Invalidate JWT access tokens if token_version is outdated (revocation upon password change)
    if not token.startswith("mv_live_"):
        token_tv = payload.get("tv")
        if token_tv is not None and token_tv < (user.token_version or 1):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked due to a password change. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token_sid = payload.get("sid")
        if token_sid:
            session_query = select(UserSession).where(
                UserSession.id == token_sid,
                UserSession.user_id == user.id,
            )
            session_rec = (await db.execute(session_query)).scalar_one_or_none()
            if not session_rec or session_rec.is_revoked:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session has been revoked.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if request is not None:
                request.state.current_session_id = token_sid

    return user


async def get_optional_current_user(
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    auth_header: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
) -> User | None:
    token: str | None = None
    if auth_header and auth_header.credentials:
        token = auth_header.credentials
    elif access_token_cookie:
        token = access_token_cookie

    if not token:
        return None

    user_id: str | None = None
    if token.startswith("mv_live_"):
        token_h = hash_token(token)
        query_token = select(APIToken).where(
            APIToken.token_hash == token_h,
            APIToken.is_revoked.is_(False),
        )
        token_record = (await db.execute(query_token)).scalar_one_or_none()
        is_expired = False
        if token_record and token_record.expires_at:
            if token_record.expires_at.tzinfo is None:
                is_expired = token_record.expires_at < datetime.utcnow()
            else:
                is_expired = token_record.expires_at < datetime.now(UTC)

        if not token_record or is_expired:
            return None
        user_id = token_record.user_id
        if request is not None:
            request.state.api_token_scopes = token_record.scopes
    else:
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None

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
    if not user or not user.is_active:
        return None

    # Invalidate JWT access tokens if token_version is outdated (revocation upon password change)
    if not token.startswith("mv_live_"):
        token_tv = payload.get("tv")
        if token_tv is not None and token_tv < (user.token_version or 1):
            return None

        token_sid = payload.get("sid")
        if token_sid:
            session_query = select(UserSession).where(
                UserSession.id == token_sid,
                UserSession.user_id == user.id,
            )
            session_rec = (await db.execute(session_query)).scalar_one_or_none()
            if not session_rec or session_rec.is_revoked:
                return None
            if request is not None:
                request.state.current_session_id = token_sid

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


def require_scope(required_scope: str):
    """
    Least-privilege RBAC guard for programmatic API tokens.
    If authenticated via programmatic API token (mv_live_...), verifies that the token
    possesses the specified required_scope or wildcard '*'.
    Standard interactive browser sessions (JWTs) bypass this check.
    """

    async def _verify_scope(
        request: Request = None,
        _user: User = Depends(get_current_active_user),
    ) -> None:
        if request is not None:
            token_scopes = getattr(request.state, "api_token_scopes", None)
            if token_scopes is not None:
                if "*" not in token_scopes and required_scope not in token_scopes:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"API token does not possess the required scope '{required_scope}'.",
                    )

    return _verify_scope


async def get_current_active_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have administrative privileges.",
        )
    return current_user


async def get_current_workspace(
    request: Request = None,
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """Resolve the active workspace for the current request.
    If X-Workspace-ID is provided, verify membership.
    Otherwise, fall back to the user's first available workspace.
    Enforces IP allowlist & CIDR geofencing policy if configured on workspace.
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

    # Enforce Workspace IP Allowlist & CIDR Geofencing Policy
    if workspace.settings and isinstance(workspace.settings, dict):
        allowlist = workspace.settings.get("ip_allowlist")
        if allowlist and request is not None:
            from app.core.ip_policy import is_ip_allowed_in_workspace

            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                client_ip = forwarded.split(",")[0].strip()
            elif request.client and request.client.host:
                client_ip = request.client.host
            else:
                client_ip = "127.0.0.1"

            if not is_ip_allowed_in_workspace(client_ip, allowlist):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: Client IP '{client_ip}' is not permitted by workspace IP security policy.",
                )

    return workspace
