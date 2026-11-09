import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_mfa_backup_codes,
    generate_totp_secret,
    get_totp_uri,
    hash_backup_code,
    hash_password,
    hash_token,
    verify_password,
    verify_totp_code,
)
from app.models.user import (
    PasswordResetToken,
    User,
    UserProfile,
    UserSession,
    UserVerificationToken,
)
from app.models.workspace import (
    Workspace,
    WorkspaceMember,
    WorkspacePlan,
    WorkspaceRole,
)
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text or "workspace"


def parse_device_info(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    os_name = "Unknown OS"
    if "macintosh" in ua or "mac os x" in ua:
        os_name = "macOS"
    elif "windows" in ua:
        os_name = "Windows"
    elif "iphone" in ua or "ipad" in ua:
        os_name = "iOS"
    elif "android" in ua:
        os_name = "Android"
    elif "linux" in ua:
        os_name = "Linux"

    browser = "Browser"
    if "edg/" in ua:
        browser = "Microsoft Edge"
    elif "chrome" in ua and "safari" in ua:
        browser = "Chrome"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "safari" in ua:
        browser = "Safari"
    elif "curl" in ua or "python" in ua or "httpx" in ua:
        browser = "API Client"

    if os_name == "Unknown OS" and browser == "Browser":
        return user_agent[:32] if user_agent else "Web Session"
    return f"{browser} on {os_name}"


class AuthService:
    @staticmethod
    async def register_user(
        db: AsyncSession, req: RegisterRequest
    ) -> tuple[User, TokenResponse, Workspace]:
        # Check if email is already registered
        query = select(User).where(User.email == req.email.lower())
        result = await db.execute(query)
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email address already exists.",
            )

        # Create user
        user = User(
            email=req.email.lower(),
            hashed_password=hash_password(req.password),
            full_name=req.full_name or req.email.split("@")[0],
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        await db.flush()

        # Create user profile
        profile = UserProfile(
            user_id=user.id,
            bio="",
            avatar_url="",
            preferences={},
        )
        db.add(profile)
        user.profile = profile

        # Create personal default workspace
        ws_name = req.workspace_name or f"{user.full_name}'s Workspace"
        base_slug = slugify(ws_name)
        slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
        workspace = Workspace(
            name=ws_name,
            slug=slug,
            description="Personal knowledge workspace",
            owner_id=user.id,
            plan_tier=WorkspacePlan.FREE,
            settings={},
        )
        db.add(workspace)
        await db.flush()

        # Add user as OWNER of the workspace
        membership = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
        )
        db.add(membership)

        # Create session and tokens
        session = UserSession(
            user_id=user.id,
            refresh_token_hash="pending",
            user_agent="Registration",
            ip_address="127.0.0.1",
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            is_revoked=False,
        )
        db.add(session)
        await db.flush()

        refresh_token = create_refresh_token(subject=user.id, session_id=session.id)
        session.refresh_token_hash = hash_token(refresh_token)

        access_token = create_access_token(
            subject=user.id,
            claims={
                "email": user.email,
                "workspace_id": workspace.id,
                "is_superuser": user.is_superuser,
                "tv": user.token_version,
                "sid": session.id,
            },
        )

        tokens = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=refresh_token,
        )

        return user, tokens, workspace

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        req: LoginRequest,
        user_agent: str = "",
        ip_address: str = "",
    ) -> tuple[User, TokenResponse | None, str | None, str | None]:
        # Fetch user with memberships
        query = (
            select(User)
            .options(
                selectinload(User.profile),
                selectinload(User.workspace_memberships),
            )
            .where(User.email == req.email.lower())
        )
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if user:
            # Check account lockout status
            if user.locked_until:
                locked_until_tz = (
                    user.locked_until.replace(tzinfo=UTC)
                    if user.locked_until.tzinfo is None
                    else user.locked_until
                )
                if locked_until_tz > datetime.now(UTC):
                    remaining_seconds = int((locked_until_tz - datetime.now(UTC)).total_seconds())
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=(
                            "Account is temporarily locked due to consecutive failed login attempts. "
                            f"Try again in {max(1, remaining_seconds // 60)} minutes."
                        ),
                        headers={"Retry-After": str(max(1, remaining_seconds))},
                    )
                else:
                    user.locked_until = None
                    user.failed_login_attempts = 0

            # Verify password
            if not verify_password(req.password, user.hashed_password):
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_ATTEMPTS:
                    user.locked_until = datetime.now(UTC) + timedelta(
                        minutes=settings.ACCOUNT_LOCKOUT_MINUTES
                    )
                    await db.commit()
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=(
                            "Account is temporarily locked for 15 minutes due to 5 consecutive "
                            "failed login attempts."
                        ),
                        headers={"Retry-After": str(settings.ACCOUNT_LOCKOUT_MINUTES * 60)},
                    )
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect email or password.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Successful password verification: reset failed attempts
            if user.failed_login_attempts > 0 or user.locked_until is not None:
                user.failed_login_attempts = 0
                user.locked_until = None
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated.",
            )

        # Find default workspace ID
        default_workspace_id = None
        if user.workspace_memberships:
            default_workspace_id = user.workspace_memberships[0].workspace_id

        # If 2FA/MFA is enabled, do not issue complete session yet; issue temporary MFA challenge token
        if user.is_mfa_enabled:
            mfa_token = create_access_token(
                subject=user.id,
                claims={
                    "scope": "mfa_pending",
                    "email": user.email,
                    "tv": user.token_version,
                },
                expires_delta=timedelta(minutes=5),
            )
            return user, None, default_workspace_id, mfa_token

        # Create session
        session = UserSession(
            user_id=user.id,
            refresh_token_hash="pending",
            user_agent=user_agent[:512],
            ip_address=ip_address[:64],
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            is_revoked=False,
        )
        db.add(session)
        await db.flush()

        refresh_token = create_refresh_token(subject=user.id, session_id=session.id)
        session.refresh_token_hash = hash_token(refresh_token)

        claims = {
            "email": user.email,
            "is_superuser": user.is_superuser,
            "tv": user.token_version,
            "sid": session.id,
        }
        if default_workspace_id:
            claims["workspace_id"] = default_workspace_id

        access_token = create_access_token(subject=user.id, claims=claims)

        tokens = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=refresh_token,
        )

        return user, tokens, default_workspace_id, None

    @staticmethod
    async def setup_mfa(db: AsyncSession, user: User) -> tuple[str, str]:
        """Generate a new TOTP secret and QR code URI for the user."""
        secret = generate_totp_secret()
        user.mfa_secret = secret
        await db.commit()
        await db.refresh(user)
        uri = get_totp_uri(secret, user.email)
        return secret, uri

    @staticmethod
    async def enable_mfa(db: AsyncSession, user: User, code: str) -> list[str]:
        """Validate 6-digit TOTP code, generate single-use backup recovery codes, and enable MFA."""
        if not user.mfa_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA setup has not been initiated. Call /mfa/setup first.",
            )
        if not verify_totp_code(user.mfa_secret, code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid MFA verification code.",
            )
        user.is_mfa_enabled = True
        backup_codes = generate_mfa_backup_codes(count=8)
        user.mfa_backup_codes = [hash_backup_code(c) for c in backup_codes]
        await db.commit()
        await db.refresh(user)
        return backup_codes

    @staticmethod
    async def disable_mfa(db: AsyncSession, user: User, password: str, code: str) -> bool:
        """Disable MFA after verifying current password and 6-digit TOTP code."""
        if not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect account password.",
            )
        if not user.is_mfa_enabled or not user.mfa_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is not currently enabled on this account.",
            )
        if not verify_totp_code(user.mfa_secret, code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid MFA verification code.",
            )
        user.is_mfa_enabled = False
        user.mfa_secret = None
        user.mfa_backup_codes = []
        await db.commit()
        await db.refresh(user)
        return True

    @staticmethod
    async def authenticate_mfa(
        db: AsyncSession,
        mfa_token: str,
        code: str,
        user_agent: str = "",
        ip_address: str = "",
    ) -> tuple[User, TokenResponse, str | None]:
        """Verify temporary MFA challenge token + 6-digit TOTP code, then issue session and tokens."""
        payload = decode_token(mfa_token)
        if not payload or payload.get("scope") != "mfa_pending":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired MFA authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = payload.get("sub")
        token_version = payload.get("tv")

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

        if not user or not user.is_active or user.token_version != token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session or user account inactive.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_mfa_enabled or not user.mfa_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is not enabled for this user.",
            )

        # Check account lockout status
        if user.locked_until:
            locked_until_tz = (
                user.locked_until.replace(tzinfo=UTC)
                if user.locked_until.tzinfo is None
                else user.locked_until
            )
            if locked_until_tz > datetime.now(UTC):
                remaining_seconds = int((locked_until_tz - datetime.now(UTC)).total_seconds())
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        "Account is temporarily locked due to consecutive failed login attempts. "
                        f"Try again in {max(1, remaining_seconds // 60)} minutes."
                    ),
                    headers={"Retry-After": str(max(1, remaining_seconds))},
                )
            else:
                user.locked_until = None
                user.failed_login_attempts = 0

        # Verify TOTP code
        if not verify_totp_code(user.mfa_secret, code):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_ATTEMPTS:
                user.locked_until = datetime.now(UTC) + timedelta(
                    minutes=settings.ACCOUNT_LOCKOUT_MINUTES
                )
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Account is temporarily locked for 15 minutes due to consecutive failed login attempts.",
                    headers={"Retry-After": str(settings.ACCOUNT_LOCKOUT_MINUTES * 60)},
                )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MFA verification code.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Reset failed attempts on success
        if user.failed_login_attempts > 0 or user.locked_until is not None:
            user.failed_login_attempts = 0
            user.locked_until = None

        # Find default workspace ID
        default_workspace_id = None
        if user.workspace_memberships:
            default_workspace_id = user.workspace_memberships[0].workspace_id

        # Create session and full tokens
        session = UserSession(
            user_id=user.id,
            refresh_token_hash="pending",
            user_agent=user_agent[:512],
            ip_address=ip_address[:64],
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            is_revoked=False,
        )
        db.add(session)
        await db.flush()

        refresh_token = create_refresh_token(subject=user.id, session_id=session.id)
        session.refresh_token_hash = hash_token(refresh_token)

        claims = {
            "email": user.email,
            "is_superuser": user.is_superuser,
            "tv": user.token_version,
            "sid": session.id,
        }
        if default_workspace_id:
            claims["workspace_id"] = default_workspace_id

        access_token = create_access_token(subject=user.id, claims=claims)

        tokens = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=refresh_token,
        )

        await db.commit()
        return user, tokens, default_workspace_id

    @staticmethod
    async def authenticate_mfa_recovery(
        db: AsyncSession,
        mfa_token: str,
        recovery_code: str,
        user_agent: str = "",
        ip_address: str = "",
    ) -> tuple[User, TokenResponse, str | None]:
        """Verify temporary MFA challenge token + single-use backup recovery code, burn code, and issue session."""
        payload = decode_token(mfa_token)
        if not payload or payload.get("scope") != "mfa_pending":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired MFA authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = payload.get("sub")
        token_version = payload.get("tv")

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

        if not user or not user.is_active or user.token_version != token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session or user account inactive.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_mfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is not enabled for this user.",
            )

        # Check account lockout status
        if user.locked_until:
            locked_until_tz = (
                user.locked_until.replace(tzinfo=UTC)
                if user.locked_until.tzinfo is None
                else user.locked_until
            )
            if locked_until_tz > datetime.now(UTC):
                remaining_seconds = int((locked_until_tz - datetime.now(UTC)).total_seconds())
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        "Account is temporarily locked due to consecutive failed login attempts. "
                        f"Try again in {max(1, remaining_seconds // 60)} minutes."
                    ),
                    headers={"Retry-After": str(max(1, remaining_seconds))},
                )
            else:
                user.locked_until = None
                user.failed_login_attempts = 0

        # Check backup recovery code
        code_hash = hash_backup_code(recovery_code)
        active_codes = list(user.mfa_backup_codes or [])
        if code_hash not in active_codes:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_ATTEMPTS:
                user.locked_until = datetime.now(UTC) + timedelta(
                    minutes=settings.ACCOUNT_LOCKOUT_MINUTES
                )
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Account is temporarily locked for 15 minutes due to consecutive failed login attempts.",
                    headers={"Retry-After": str(settings.ACCOUNT_LOCKOUT_MINUTES * 60)},
                )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or already used backup recovery code.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Single-use burn: remove code hash and update JSON
        active_codes.remove(code_hash)
        user.mfa_backup_codes = active_codes

        # Reset failed attempts on success
        if user.failed_login_attempts > 0 or user.locked_until is not None:
            user.failed_login_attempts = 0
            user.locked_until = None

        # Find default workspace ID
        default_workspace_id = None
        if user.workspace_memberships:
            default_workspace_id = user.workspace_memberships[0].workspace_id

        # Create session and full tokens
        session = UserSession(
            user_id=user.id,
            refresh_token_hash="pending",
            user_agent=user_agent[:512],
            ip_address=ip_address[:64],
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            is_revoked=False,
        )
        db.add(session)
        await db.flush()

        refresh_token = create_refresh_token(subject=user.id, session_id=session.id)
        session.refresh_token_hash = hash_token(refresh_token)

        claims = {
            "email": user.email,
            "is_superuser": user.is_superuser,
            "tv": user.token_version,
            "sid": session.id,
        }
        if default_workspace_id:
            claims["workspace_id"] = default_workspace_id

        access_token = create_access_token(subject=user.id, claims=claims)

        tokens = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=refresh_token,
        )

        await db.commit()
        return user, tokens, default_workspace_id

    @staticmethod
    async def regenerate_backup_codes(
        db: AsyncSession,
        user: User,
        password: str,
        code: str,
    ) -> list[str]:
        """Verify password + TOTP code and regenerate 8 new single-use recovery codes."""
        if not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect account password.",
            )
        if not user.is_mfa_enabled or not user.mfa_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is not currently enabled on this account.",
            )
        if not verify_totp_code(user.mfa_secret, code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid MFA verification code.",
            )

        new_codes = generate_mfa_backup_codes(count=8)
        user.mfa_backup_codes = [hash_backup_code(c) for c in new_codes]
        await db.commit()
        await db.refresh(user)
        return new_codes

    @staticmethod
    async def refresh_session(db: AsyncSession, refresh_token: str) -> tuple[TokenResponse, str]:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token.",
            )

        user_id = payload.get("sub")
        session_id = payload.get("sid")
        if not user_id or not session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed token claims.",
            )

        query = select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
        )
        result = await db.execute(query)
        session = result.scalar_one_or_none()

        if not session or session.is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked.",
            )

        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has expired. Please log in again.",
            )

        # Verify token hash matches stored hash
        if session.refresh_token_hash != hash_token(refresh_token):
            # Possible token reuse/replay attack: revoke session immediately
            session.is_revoked = True
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token validation failed. Session revoked.",
            )

        # Rotate refresh token
        new_refresh_token = create_refresh_token(subject=user_id, session_id=session.id)
        session.refresh_token_hash = hash_token(new_refresh_token)

        # Generate new access token
        user_query = (
            select(User).options(selectinload(User.workspace_memberships)).where(User.id == user_id)
        )
        user_res = await db.execute(user_query)
        user = user_res.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User inactive or not found.",
            )

        default_workspace_id = (
            user.workspace_memberships[0].workspace_id if user.workspace_memberships else None
        )

        claims = {
            "email": user.email,
            "is_superuser": user.is_superuser,
            "tv": user.token_version,
            "sid": session.id,
        }
        if default_workspace_id:
            claims["workspace_id"] = default_workspace_id

        new_access_token = create_access_token(subject=user.id, claims=claims)

        tokens = TokenResponse(
            access_token=new_access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=new_refresh_token,
        )

        return tokens, user_id

    @staticmethod
    async def revoke_session(db: AsyncSession, session_id: str, user_id: str) -> bool:
        query = select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
        )
        result = await db.execute(query)
        session = result.scalar_one_or_none()
        if session:
            session.is_revoked = True
            await db.commit()
            return True
        return False

    @staticmethod
    async def list_user_sessions(
        db: AsyncSession, user_id: str, current_session_id: str | None = None
    ) -> list[dict]:
        """List active unrevoked sessions for the user with device context."""
        query = (
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.is_revoked.is_(False),
            )
            .order_by(UserSession.created_at.desc())
        )
        sessions = (await db.execute(query)).scalars().all()
        result = []
        for s in sessions:
            device = parse_device_info(s.user_agent)
            result.append(
                {
                    "id": s.id,
                    "ip_address": s.ip_address or "Unknown IP",
                    "user_agent": s.user_agent or "Unknown Client",
                    "device_info": device,
                    "is_current": (s.id == current_session_id) if current_session_id else False,
                    "created_at": s.created_at,
                    "expires_at": s.expires_at,
                }
            )
        return result

    @staticmethod
    async def revoke_other_sessions(
        db: AsyncSession, user_id: str, current_session_id: str | None
    ) -> int:
        """Revoke all active sessions belonging to user except the current one."""
        query = select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.is_revoked.is_(False),
        )
        if current_session_id:
            query = query.where(UserSession.id != current_session_id)
        sessions = (await db.execute(query)).scalars().all()
        count = 0
        for s in sessions:
            s.is_revoked = True
            count += 1
        await db.commit()
        return count

    @staticmethod
    async def request_password_reset(db: AsyncSession, email: str) -> str:
        """Create a password reset token for the given user email."""
        query = select(User).where(User.email == email.lower())
        res = await db.execute(query)
        user = res.scalar_one_or_none()
        if not user:
            # Prevent user enumeration by returning a fake token or generic success
            return "reset_token_dispatched"

        # Invalidate any previously pending unused reset tokens for this user
        revoke_old_tokens = (
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.is_used.is_(False),
            )
            .values(is_used=True)
        )
        await db.execute(revoke_old_tokens)

        raw_token = secrets.token_urlsafe(32)
        token_record = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            is_used=False,
        )
        db.add(token_record)
        await db.commit()
        return raw_token

    @staticmethod
    async def reset_password(db: AsyncSession, raw_token: str, new_password: str) -> bool:
        """Verify token and update password, revoking existing sessions."""
        hashed = hash_token(raw_token)
        query = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hashed,
            PasswordResetToken.is_used.is_(False),
        )
        res = await db.execute(query)
        token_record = res.scalar_one_or_none()

        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token.",
            )

        expires_at = token_record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has expired.",
            )

        user_query = select(User).where(User.id == token_record.user_id)
        user = (await db.execute(user_query)).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        # Update password and increment token_version for immediate JWT revocation
        user.hashed_password = hash_password(new_password)
        user.password_changed_at = datetime.now(UTC)
        user.token_version = (user.token_version or 1) + 1
        token_record.is_used = True

        # Invalidate all active sessions for security
        session_query = select(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.is_revoked.is_(False),
        )
        sessions = (await db.execute(session_query)).scalars().all()
        for s in sessions:
            s.is_revoked = True

        await db.commit()
        return True

    @staticmethod
    async def request_email_verification(db: AsyncSession, user_id: str) -> str:
        # Invalidate any previously pending unused verification tokens for this user
        revoke_old_tokens = (
            update(UserVerificationToken)
            .where(
                UserVerificationToken.user_id == user_id,
                UserVerificationToken.is_used.is_(False),
            )
            .values(is_used=True)
        )
        await db.execute(revoke_old_tokens)

        raw_token = secrets.token_urlsafe(32)
        record = UserVerificationToken(
            user_id=user_id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
            is_used=False,
        )
        db.add(record)
        await db.commit()
        return raw_token

    @staticmethod
    async def verify_email(db: AsyncSession, raw_token: str) -> bool:
        hashed = hash_token(raw_token)
        query = select(UserVerificationToken).where(
            UserVerificationToken.token_hash == hashed,
            UserVerificationToken.is_used.is_(False),
        )
        res = await db.execute(query)
        record = res.scalar_one_or_none()

        if not record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification token.",
            )

        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token has expired.",
            )

        user_query = select(User).where(User.id == record.user_id)
        user = (await db.execute(user_query)).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        user.is_verified = True
        record.is_used = True
        await db.commit()
        return True

    @staticmethod
    async def delete_user_account(db: AsyncSession, user_id: str) -> bool:
        """Cascade permanent deletion of user account, owned workspaces, and storage records."""
        query = select(User).where(User.id == user_id)
        res = await db.execute(query)
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        # 1. Clean up workspaces owned by the user (including S3/MinIO physical storage files)
        from app.services.workspace_service import WorkspaceService

        ws_query = select(Workspace).where(Workspace.owner_id == user_id)
        ws_res = await db.execute(ws_query)
        owned_workspaces = ws_res.scalars().all()
        for ws in owned_workspaces:
            await WorkspaceService.delete_workspace(
                db=db,
                workspace_id=ws.id,
                current_user_id=user_id,
                is_superuser=True,
            )

        # Expire session cache so identity map syncs with cascaded database records
        await db.flush()
        db.expire_all()

        u_stmt = select(User).where(User.id == user_id)
        u_to_delete = (await db.execute(u_stmt)).scalar_one_or_none()
        if u_to_delete:
            await db.delete(u_to_delete)
        await db.commit()
        return True

    @staticmethod
    async def change_password(
        db: AsyncSession,
        user: User,
        current_password: str,
        new_password: str,
        user_agent: str = "",
        ip_address: str = "",
    ) -> tuple[TokenResponse, User]:
        """Change user password, revoke previous sessions and bump token_version for instant JWT invalidation."""
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect.",
            )

        if current_password == new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password cannot be identical to the current password.",
            )

        user.hashed_password = hash_password(new_password)
        user.password_changed_at = datetime.now(UTC)
        user.token_version = (user.token_version or 1) + 1

        # Invalidate all existing sessions
        session_query = select(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.is_revoked.is_(False),
        )
        sessions = (await db.execute(session_query)).scalars().all()
        for s in sessions:
            s.is_revoked = True

        # Create new session
        session = UserSession(
            user_id=user.id,
            refresh_token_hash="pending",
            user_agent=user_agent[:512],
            ip_address=ip_address[:64],
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            is_revoked=False,
        )
        db.add(session)
        await db.flush()

        refresh_token = create_refresh_token(subject=user.id, session_id=session.id)
        session.refresh_token_hash = hash_token(refresh_token)

        default_workspace_id = None
        if user.workspace_memberships:
            default_workspace_id = user.workspace_memberships[0].workspace_id

        claims = {
            "email": user.email,
            "is_superuser": user.is_superuser,
            "tv": user.token_version,
            "sid": session.id,
        }
        if default_workspace_id:
            claims["workspace_id"] = default_workspace_id

        access_token = create_access_token(subject=user.id, claims=claims)
        tokens = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=refresh_token,
        )

        await db.commit()
        await db.refresh(user)
        return tokens, user
