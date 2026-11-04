
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.common import APIResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def set_auth_cookies(response: Response, tokens: TokenResponse):
    """Securely set access and refresh token cookies."""
    response.set_cookie(
        key="access_token",
        value=tokens.access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        domain=settings.COOKIE_DOMAIN or None,
    )
    if tokens.refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=tokens.refresh_token,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            domain=settings.COOKIE_DOMAIN or None,
        )


def clear_auth_cookies(response: Response):
    """Clear session cookies upon logout."""
    response.delete_cookie("access_token", domain=settings.COOKIE_DOMAIN or None)
    response.delete_cookie("refresh_token", domain=settings.COOKIE_DOMAIN or None)


@router.post("/register", response_model=APIResponse[dict], status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user, tokens, workspace = await AuthService.register_user(db, req)
    set_auth_cookies(response, tokens)

    return APIResponse(
        success=True,
        data={
            "user": UserResponse.model_validate(user),
            "tokens": tokens,
            "workspace": {
                "id": workspace.id,
                "name": workspace.name,
                "slug": workspace.slug,
            },
        },
    )


@router.post("/login", response_model=APIResponse[dict])
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user_agent = request.headers.get("user-agent", "")
    ip_address = request.client.host if request.client else ""

    user, tokens, default_workspace_id = await AuthService.authenticate_user(
        db, req, user_agent=user_agent, ip_address=ip_address
    )
    set_auth_cookies(response, tokens)

    return APIResponse(
        success=True,
        data={
            "user": UserResponse.model_validate(user),
            "tokens": tokens,
            "default_workspace_id": default_workspace_id,
        },
    )


@router.post("/refresh", response_model=APIResponse[TokenResponse])
async def refresh_token(
    response: Response,
    body: RefreshTokenRequest | None = None,
    refresh_token_cookie: str | None = Cookie(default=None, alias="refresh_token"),
    db: AsyncSession = Depends(get_db),
):
    token = (body.refresh_token if body else None) or refresh_token_cookie
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required.",
        )

    tokens, _ = await AuthService.refresh_session(db, token)
    set_auth_cookies(response, tokens)

    return APIResponse(success=True, data=tokens)


@router.post("/logout", response_model=APIResponse[dict])
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Revoke sessions for user and clear cookies
    clear_auth_cookies(response)
    return APIResponse(
        success=True,
        data={"message": "Logged out successfully."},
    )


@router.get("/me", response_model=APIResponse[UserResponse])
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return APIResponse(
        success=True,
        data=UserResponse.model_validate(current_user),
    )
