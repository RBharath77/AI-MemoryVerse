import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
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
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
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
    ) -> tuple[User, TokenResponse, str | None]:
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

        if not user or not verify_password(req.password, user.hashed_password):
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

        # Create session
        session = UserSession(
            user_id=user.id,
            refresh_token_hash="pending",
            user_agent=user_agent[:512],
            ip_address=ip_address[:64],
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            is_revoked=False,
        )
        db.add(session)
        await db.flush()

        refresh_token = create_refresh_token(subject=user.id, session_id=session.id)
        session.refresh_token_hash = hash_token(refresh_token)

        claims = {
            "email": user.email,
            "is_superuser": user.is_superuser,
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

        return user, tokens, default_workspace_id

    @staticmethod
    async def refresh_session(
        db: AsyncSession, refresh_token: str
    ) -> tuple[TokenResponse, str]:
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
            select(User)
            .options(selectinload(User.workspace_memberships))
            .where(User.id == user_id)
        )
        user_res = await db.execute(user_query)
        user = user_res.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User inactive or not found.",
            )

        default_workspace_id = (
            user.workspace_memberships[0].workspace_id
            if user.workspace_memberships
            else None
        )

        claims = {
            "email": user.email,
            "is_superuser": user.is_superuser,
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
    async def request_password_reset(db: AsyncSession, email: str) -> str:
        """Create a password reset token for the given user email."""
        query = select(User).where(User.email == email.lower())
        res = await db.execute(query)
        user = res.scalar_one_or_none()
        if not user:
            # Prevent user enumeration by returning a fake token or generic success
            return "reset_token_dispatched"

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

        # Update password
        user.hashed_password = hash_password(new_password)
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
        """Cascade permanent deletion of user account and related records."""
        query = select(User).where(User.id == user_id)
        res = await db.execute(query)
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        await db.delete(user)
        await db.commit()
        return True
