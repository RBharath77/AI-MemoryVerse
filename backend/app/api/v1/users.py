import hashlib
import json
import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.core.sanitizer import CredentialSanitizer
from app.core.ssrf import validate_url_safe
from app.models.chat import Conversation
from app.models.document import Document
from app.models.memory import Memory
from app.models.user import User, UserSession
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.common import APIResponse
from app.schemas.user import UserResponse, UserUpdateRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["Users"])


def sanitize_user_input(text: str) -> str:
    """Sanitize user input by stripping HTML/script tags and redacting sensitive credentials."""
    if not text:
        return text
    # Strip script/iframe tags and general html tags
    clean = re.sub(
        r"<(script|iframe|object|embed)[^>]*>.*?</\1>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    clean = re.sub(r"<[^>]+>", "", clean)
    clean = CredentialSanitizer.redact(clean).sanitized_text
    return clean.strip()


@router.get("/me", response_model=APIResponse[UserResponse])
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
):
    return APIResponse(
        success=True,
        data=UserResponse.model_validate(current_user),
    )


@router.patch("/me", response_model=APIResponse[UserResponse])
async def update_current_user_profile(
    data: UserUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if data.full_name is not None:
        current_user.full_name = sanitize_user_input(data.full_name)

    if data.profile and current_user.profile:
        if data.profile.bio is not None:
            current_user.profile.bio = sanitize_user_input(data.profile.bio)
        if data.profile.avatar_url is not None:
            avatar_url = data.profile.avatar_url.strip()
            if avatar_url:
                # SSRF Protection: validate avatar URL against internal/cloud metadata networks
                validate_url_safe(avatar_url)
                current_user.profile.avatar_url = avatar_url
            else:
                current_user.profile.avatar_url = ""
        if data.profile.ai_custom_instructions is not None:
            current_user.profile.ai_custom_instructions = sanitize_user_input(
                data.profile.ai_custom_instructions
            )
        if data.profile.preferences is not None:
            current_user.profile.preferences = data.profile.preferences

    await db.commit()
    await db.refresh(current_user)

    return APIResponse(
        success=True,
        data=UserResponse.model_validate(current_user),
    )


@router.get("/me/export", response_model=APIResponse[dict])
async def export_current_user_data(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """GDPR Article 20 & CCPA Data Portability export.

    Generates a structured, machine-readable JSON archive containing personal data,
    workspaces, memories, documents metadata, conversations, and security telemetry.
    """
    profile_data = {}
    if current_user.profile:
        profile_data = {
            "bio": current_user.profile.bio,
            "avatar_url": current_user.profile.avatar_url,
            "ai_custom_instructions": current_user.profile.ai_custom_instructions,
            "preferences": current_user.profile.preferences or {},
        }

    account_info = {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "is_mfa_enabled": current_user.is_mfa_enabled,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "profile": profile_data,
    }

    # Workspaces
    ws_stmt = (
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == current_user.id)
    )
    ws_results = (await db.execute(ws_stmt)).all()
    workspaces_list = [
        {
            "id": w.id,
            "name": w.name,
            "slug": w.slug,
            "role": role.value if hasattr(role, "value") else str(role),
            "plan_tier": w.plan_tier.value if hasattr(w.plan_tier, "value") else str(w.plan_tier),
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w, role in ws_results
    ]

    # Memories
    mem_stmt = select(Memory).where(Memory.user_id == current_user.id)
    mem_results = (await db.execute(mem_stmt)).scalars().all()
    memories_list = [
        {
            "id": m.id,
            "workspace_id": m.workspace_id,
            "content": m.content,
            "category": m.category.value if hasattr(m.category, "value") else str(m.category),
            "status": m.status.value if hasattr(m.status, "value") else str(m.status),
            "importance": m.importance,
            "confidence": m.confidence,
            "tags": m.tags or [],
            "is_pinned": m.is_pinned,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in mem_results
    ]

    # Documents metadata
    doc_stmt = select(Document).where(Document.user_id == current_user.id)
    doc_results = (await db.execute(doc_stmt)).scalars().all()
    documents_list = [
        {
            "id": d.id,
            "workspace_id": d.workspace_id,
            "title": d.title,
            "filename": d.filename,
            "file_size": d.file_size,
            "mime_type": d.mime_type,
            "status": d.status.value if hasattr(d.status, "value") else str(d.status),
            "word_count": d.word_count,
            "token_count": d.token_count,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in doc_results
    ]

    # Conversations & Messages
    conv_stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.user_id == current_user.id)
    )
    conv_results = (await db.execute(conv_stmt)).scalars().all()
    conversations_list = [
        {
            "id": c.id,
            "workspace_id": c.workspace_id,
            "title": c.title,
            "model": c.model,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "citations": msg.citations or [],
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
                for msg in (c.messages or [])
            ],
        }
        for c in conv_results
    ]

    # Sessions
    session_stmt = select(UserSession).where(UserSession.user_id == current_user.id)
    session_results = (await db.execute(session_stmt)).scalars().all()
    sessions_list = [
        {
            "id": s.id,
            "user_agent": s.user_agent,
            "ip_address": s.ip_address,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in session_results
    ]

    export_payload = {
        "account": account_info,
        "workspaces": workspaces_list,
        "memories": memories_list,
        "documents": documents_list,
        "conversations": conversations_list,
        "sessions": sessions_list,
        "metadata": {
            "exported_at": datetime.now(UTC).isoformat(),
            "compliance_standard": "GDPR Article 20 / CCPA Right to Portability",
            "format_version": "1.0",
        },
    }

    # Compute SHA-256 integrity signature
    serialized = json.dumps(export_payload, sort_keys=True)
    integrity_checksum = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    export_payload["metadata"]["integrity_sha256"] = integrity_checksum

    return APIResponse(success=True, data=export_payload)


@router.delete("/me", response_model=APIResponse[dict])
async def delete_current_user_account(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """GDPR-compliant permanent account deletion with cascade cleanup."""
    await AuthService.delete_user_account(db, current_user.id)
    return APIResponse(
        success=True,
        data={
            "message": (
                "User account and all associated personal data have been permanently deleted."
            )
        },
    )
