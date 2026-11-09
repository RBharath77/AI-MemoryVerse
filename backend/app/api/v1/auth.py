from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import RateLimiter
from app.core.security import create_access_token, hash_password
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MFAAuthenticateRequest,
    MFABackupCodesCountResponse,
    MFABackupCodesResponse,
    MFADisableRequest,
    MFARecoveryRequest,
    MFARegenerateBackupCodesRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserSessionResponse,
    VerifyEmailRequest,
)
from app.schemas.common import APIResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])
auth_rate_limiter = RateLimiter(times=10, seconds=60)


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
    _rate_limit: None = Depends(auth_rate_limiter),
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
    _rate_limit: None = Depends(auth_rate_limiter),
):
    user_agent = request.headers.get("user-agent", "")
    ip_address = request.client.host if request.client else ""

    user, tokens, default_workspace_id, mfa_token = await AuthService.authenticate_user(
        db, req, user_agent=user_agent, ip_address=ip_address
    )

    if mfa_token:
        return APIResponse(
            success=True,
            data={
                "mfa_required": True,
                "mfa_token": mfa_token,
                "user_id": user.id,
            },
        )

    set_auth_cookies(response, tokens)

    return APIResponse(
        success=True,
        data={
            "mfa_required": False,
            "user": UserResponse.model_validate(user),
            "tokens": tokens,
            "default_workspace_id": default_workspace_id,
        },
    )


@router.post("/mfa/setup", response_model=APIResponse[MFASetupResponse])
async def setup_mfa(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new TOTP secret and QR URI for user 2FA setup."""
    secret, uri = await AuthService.setup_mfa(db, current_user)
    return APIResponse(
        success=True,
        data=MFASetupResponse(secret=secret, totp_uri=uri),
    )


@router.post("/mfa/enable", response_model=APIResponse[dict])
async def enable_mfa(
    req: MFAVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify code, activate 2FA, and return single-use backup recovery codes."""
    backup_codes = await AuthService.enable_mfa(db, current_user, req.code)
    return APIResponse(
        success=True,
        data={
            "message": "Two-factor authentication has been successfully enabled.",
            "backup_codes": backup_codes,
            "count": len(backup_codes),
        },
    )


@router.get("/mfa/backup-codes", response_model=APIResponse[MFABackupCodesCountResponse])
async def get_backup_codes_count(
    current_user: User = Depends(get_current_user),
):
    """Get the number of remaining single-use backup recovery codes."""
    return APIResponse(
        success=True,
        data=MFABackupCodesCountResponse(count=len(current_user.mfa_backup_codes or [])),
    )


@router.post("/mfa/backup-codes/regenerate", response_model=APIResponse[MFABackupCodesResponse])
async def regenerate_backup_codes(
    req: MFARegenerateBackupCodesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Regenerate 8 new single-use backup recovery codes after validating password + TOTP."""
    codes = await AuthService.regenerate_backup_codes(db, current_user, req.password, req.code)
    return APIResponse(
        success=True,
        data=MFABackupCodesResponse(backup_codes=codes, count=len(codes)),
    )


@router.post("/mfa/disable", response_model=APIResponse[dict])
async def disable_mfa(
    req: MFADisableRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disable 2FA after validating current account password and 6-digit TOTP code."""
    await AuthService.disable_mfa(db, current_user, req.password, req.code)
    return APIResponse(
        success=True,
        data={"message": "Two-factor authentication has been successfully disabled."},
    )


@router.post("/mfa/authenticate", response_model=APIResponse[dict])
async def authenticate_mfa(
    req: MFAAuthenticateRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(auth_rate_limiter),
):
    """Complete 2FA login challenge with temporary MFA token + 6-digit TOTP code."""
    user_agent = request.headers.get("user-agent", "")
    ip_address = request.client.host if request.client else ""

    user, tokens, default_workspace_id = await AuthService.authenticate_mfa(
        db=db,
        mfa_token=req.mfa_token,
        code=req.code,
        user_agent=user_agent,
        ip_address=ip_address,
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


@router.post("/mfa/recovery", response_model=APIResponse[dict])
async def authenticate_mfa_recovery(
    req: MFARecoveryRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(auth_rate_limiter),
):
    """Complete 2FA login challenge using single-use backup recovery code."""
    user_agent = request.headers.get("user-agent", "")
    ip_address = request.client.host if request.client else ""

    user, tokens, default_workspace_id = await AuthService.authenticate_mfa_recovery(
        db=db,
        mfa_token=req.mfa_token,
        recovery_code=req.recovery_code,
        user_agent=user_agent,
        ip_address=ip_address,
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


@router.get("/sessions", response_model=APIResponse[list[UserSessionResponse]])
async def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active unrevoked sessions for the authenticated user."""
    current_sid = getattr(request.state, "current_session_id", None)
    sessions = await AuthService.list_user_sessions(db, current_user.id, current_sid)
    return APIResponse(
        success=True,
        data=[UserSessionResponse.model_validate(s) for s in sessions],
    )


@router.delete("/sessions/other", response_model=APIResponse[dict])
async def revoke_other_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke all sessions belonging to the current user except the active session."""
    current_sid = getattr(request.state, "current_session_id", None)
    count = await AuthService.revoke_other_sessions(db, current_user.id, current_sid)
    return APIResponse(
        success=True,
        data={
            "message": f"Successfully revoked {count} other active session(s).",
            "revoked_count": count,
        },
    )


@router.delete("/sessions/{session_id}", response_model=APIResponse[dict])
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a specific user session remotely."""
    success = await AuthService.revoke_session(db, session_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or already revoked.",
        )
    return APIResponse(
        success=True,
        data={"message": "Session successfully revoked."},
    )


@router.post("/demo", response_model=APIResponse[dict])
async def demo_auth(
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Frictionless authentication for sandbox exploration if explicitly enabled."""
    if not settings.ALLOW_DEMO_LOGIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo authentication is disabled in this environment.",
        )

    # Dedicated isolated sandbox user, never the root admin
    demo_email = "sandbox.demo@memoryverse.ai"
    u_res = await db.execute(select(User).where(User.email == demo_email))
    user = u_res.scalars().first()
    if not user:
        user = User(
            email=demo_email,
            hashed_password=hash_password("SandboxDemoPass123!"),
            full_name="Sandbox Explorer",
            is_active=True,
            is_verified=True,
            is_superuser=False,
        )
        db.add(user)
        await db.flush()

    w_res = await db.execute(select(Workspace).where(Workspace.owner_id == user.id).limit(1))
    workspace = w_res.scalars().first()
    if not workspace:
        workspace = Workspace(
            name="Sandbox Workspace",
            slug=f"sandbox-{user.id[:8]}",
            owner_id=user.id,
        )
        db.add(workspace)
        await db.flush()
    await db.commit()

    tokens = TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=None,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    set_auth_cookies(response, tokens)

    return APIResponse(
        success=True,
        data={
            "user": UserResponse.model_validate(user),
            "tokens": tokens,
            "default_workspace_id": workspace.id,
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


@router.post("/forgot-password", response_model=APIResponse[dict])
async def forgot_password(
    req: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(auth_rate_limiter),
):
    token = await AuthService.request_password_reset(db, req.email)
    return APIResponse(
        success=True,
        data={
            "message": "If this email is registered, a password reset link has been dispatched.",
            "debug_token": token if settings.APP_ENV == "test" else None,
        },
    )


@router.post("/reset-password", response_model=APIResponse[dict])
async def reset_password(
    req: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    await AuthService.reset_password(db, req.token, req.new_password)
    return APIResponse(
        success=True,
        data={
            "message": (
                "Password has been successfully reset. Please log in with your new credentials."
            )
        },
    )


@router.post("/verify-email", response_model=APIResponse[dict])
async def verify_email(
    req: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    await AuthService.verify_email(db, req.token)
    return APIResponse(
        success=True,
        data={"message": "Email address successfully verified."},
    )


@router.post("/request-verification", response_model=APIResponse[dict])
async def request_verification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    token = await AuthService.request_email_verification(db, current_user.id)
    return APIResponse(
        success=True,
        data={
            "message": "Verification link dispatched to registered email.",
            "debug_token": token if settings.APP_ENV == "test" else None,
        },
    )


@router.post("/change-password", response_model=APIResponse[TokenResponse])
async def change_password(
    req: ChangePasswordRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change account password with current credentials, revoking older sessions and bumping token_version."""
    tokens, _ = await AuthService.change_password(
        db=db,
        user=current_user,
        current_password=req.current_password,
        new_password=req.new_password,
        user_agent=request.headers.get("user-agent", ""),
        ip_address=request.client.host if request.client else "",
    )
    set_auth_cookies(response, tokens)
    return APIResponse(
        success=True,
        data=tokens,
    )
