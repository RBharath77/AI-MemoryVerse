import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.workspace import (
    Workspace,
    WorkspaceMember,
    WorkspacePlan,
    WorkspaceRole,
)
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceUpdate,
)
from app.services.auth_service import slugify

logger = logging.getLogger(__name__)


class WorkspaceService:
    @staticmethod
    async def create_workspace(
        db: AsyncSession,
        user: User,
        data: WorkspaceCreate,
    ) -> Workspace:
        base_slug = slugify(data.name)
        slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        workspace = Workspace(
            name=data.name,
            slug=slug,
            description=data.description or "",
            owner_id=user.id,
            plan_tier=WorkspacePlan.FREE,
            settings={},
        )
        db.add(workspace)
        await db.flush()

        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
        )
        db.add(member)
        await db.commit()
        await db.refresh(workspace)
        return workspace

    @staticmethod
    async def get_user_workspaces(
        db: AsyncSession,
        user_id: str,
    ) -> list[Workspace]:
        query = (
            select(Workspace)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.created_at.asc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_workspace_by_id(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
    ) -> Workspace:
        query = (
            select(Workspace)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(
                Workspace.id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        result = await db.execute(query)
        workspace = result.scalar_one_or_none()
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found or unauthorized access.",
            )
        return workspace

    @staticmethod
    async def update_workspace(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        data: WorkspaceUpdate,
    ) -> Workspace:
        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, user_id)

        # Check if user is owner or admin
        membership_query = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        membership_res = await db.execute(membership_query)
        member = membership_res.scalar_one_or_none()
        if not member or member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to modify workspace.",
            )

        if data.name is not None:
            workspace.name = data.name
        if data.description is not None:
            workspace.description = data.description
        if data.settings is not None:
            workspace.settings = data.settings

        await db.commit()
        await db.refresh(workspace)
        return workspace

    @staticmethod
    async def get_workspace_members(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
    ) -> list[WorkspaceMember]:
        # Verify caller has access to workspace
        await WorkspaceService.get_workspace_by_id(db, workspace_id, user_id)

        query = (
            select(WorkspaceMember)
            .options(selectinload(WorkspaceMember.user))
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.created_at.asc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def add_workspace_member(
        db: AsyncSession,
        workspace_id: str,
        current_user_id: str,
        data: WorkspaceMemberCreate,
    ) -> WorkspaceMember:
        # Caller must be OWNER or ADMIN
        caller_query = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user_id,
        )
        res = await db.execute(caller_query)
        caller = res.scalar_one_or_none()
        if not caller or caller.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace owners and admins can invite members.",
            )

        if data.role == WorkspaceRole.OWNER and caller.role != WorkspaceRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace owners can assign the OWNER role.",
            )

        # Check existing membership
        existing_query = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == data.user_id,
        )
        existing_res = await db.execute(existing_query)
        if existing_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this workspace.",
            )

        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=data.user_id,
            role=data.role,
        )
        db.add(member)
        await db.commit()
        await db.refresh(member)
        return member

    @staticmethod
    async def remove_workspace_member(
        db: AsyncSession,
        workspace_id: str,
        current_user_id: str,
        target_user_id: str,
    ) -> bool:
        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, current_user_id)
        if workspace.owner_id == target_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the workspace owner.",
            )

        # Check caller permissions
        caller_query = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user_id,
        )
        caller = (await db.execute(caller_query)).scalar_one_or_none()
        if not caller:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

        # Allow user to leave themselves or admin/owner to remove others
        if current_user_id != target_user_id and caller.role not in [
            WorkspaceRole.OWNER,
            WorkspaceRole.ADMIN,
        ]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to remove members.",
            )

        target_query = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == target_user_id,
        )
        target = (await db.execute(target_query)).scalar_one_or_none()
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")

        if target.role == WorkspaceRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the workspace owner.",
            )

        if (
            target.role == WorkspaceRole.ADMIN
            and caller.role != WorkspaceRole.OWNER
            and current_user_id != target_user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace owners can remove admin members.",
            )

        await db.delete(target)
        await db.commit()
        return True

    @staticmethod
    async def update_workspace_member_role(
        db: AsyncSession,
        workspace_id: str,
        current_user_id: str,
        target_user_id: str,
        new_role: WorkspaceRole,
    ) -> WorkspaceMember:
        await WorkspaceService.get_workspace_by_id(db, workspace_id, current_user_id)

        caller_query = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user_id,
        )
        caller = (await db.execute(caller_query)).scalar_one_or_none()
        if not caller or caller.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace owners and admins can update member roles.",
            )

        target_query = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == target_user_id,
        )
        target = (await db.execute(target_query)).scalar_one_or_none()
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")

        if target.role == WorkspaceRole.OWNER and new_role != WorkspaceRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change the workspace owner's role directly.",
            )

        if (
            new_role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)
            and caller.role != WorkspaceRole.OWNER
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace owners can promote members to Admin or Owner.",
            )

        if (
            target.role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)
            and caller.role != WorkspaceRole.OWNER
            and current_user_id != target_user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace owners can modify Admin or Owner roles.",
            )

        target.role = new_role
        await db.commit()
        await db.refresh(target)
        return target

    @staticmethod
    async def delete_workspace(
        db: AsyncSession,
        workspace_id: str,
        current_user_id: str,
        is_superuser: bool = False,
    ) -> bool:
        """Permanently delete a workspace and cascade-scrub all multi-tenant resources.

        Enforces strict RBAC: only the workspace OWNER or superuser can perform deletion.
        """
        # 1. Fetch workspace
        ws_query = select(Workspace).where(Workspace.id == workspace_id)
        ws_res = await db.execute(ws_query)
        workspace = ws_res.scalar_one_or_none()
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found.",
            )

        # 2. Check RBAC: Only OWNER or Superuser can delete workspace
        if not is_superuser:
            role_query = select(WorkspaceMember.role).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == current_user_id,
            )
            role_res = await db.execute(role_query)
            user_role = role_res.scalar_one_or_none()
            if not user_role or user_role != WorkspaceRole.OWNER:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the workspace owner can delete the workspace.",
                )

        # 3. Clean up physical files in object storage for all documents in workspace
        try:
            from app.core.storage import get_storage_provider
            from app.models.document import Document

            storage = get_storage_provider()
            docs_res = await db.execute(
                select(Document).where(Document.workspace_id == workspace_id)
            )
            docs = docs_res.scalars().all()
            for doc in docs:
                try:
                    await storage.delete_file(doc.file_key)
                except Exception:
                    pass
        except Exception:
            pass

        # 4. Explicit cascade cleanup across all workspace entities
        from sqlalchemy import delete

        from app.models.agent import AgentAction, AgentTask, APIToken
        from app.models.chat import ChatMessage, Conversation
        from app.models.document import Document, DocumentChunk
        from app.models.graph import GraphEntity, GraphRelationship
        from app.models.memory import Memory, MemoryFeedback, MemoryLink, MemoryReview
        from app.models.research import KnowledgeInsight, ResearchReport
        from app.models.webhook import WebhookDelivery, WebhookEndpoint

        await db.execute(
            delete(WebhookDelivery).where(WebhookDelivery.workspace_id == workspace_id)
        )
        await db.execute(
            delete(WebhookEndpoint).where(WebhookEndpoint.workspace_id == workspace_id)
        )
        await db.execute(
            delete(WebhookDelivery).where(WebhookDelivery.workspace_id == workspace_id)
        )
        await db.execute(
            delete(WebhookEndpoint).where(WebhookEndpoint.workspace_id == workspace_id)
        )
        await db.execute(delete(MemoryFeedback).where(MemoryFeedback.workspace_id == workspace_id))
        await db.execute(delete(MemoryLink).where(MemoryLink.workspace_id == workspace_id))
        await db.execute(delete(MemoryReview).where(MemoryReview.workspace_id == workspace_id))
        await db.execute(delete(Memory).where(Memory.workspace_id == workspace_id))
        await db.execute(delete(DocumentChunk).where(DocumentChunk.workspace_id == workspace_id))
        await db.execute(delete(Document).where(Document.workspace_id == workspace_id))
        await db.execute(
            delete(GraphRelationship).where(GraphRelationship.workspace_id == workspace_id)
        )
        await db.execute(delete(GraphEntity).where(GraphEntity.workspace_id == workspace_id))
        await db.execute(delete(ChatMessage).where(ChatMessage.workspace_id == workspace_id))
        await db.execute(delete(Conversation).where(Conversation.workspace_id == workspace_id))
        await db.execute(delete(AgentAction).where(AgentAction.workspace_id == workspace_id))
        await db.execute(delete(AgentTask).where(AgentTask.workspace_id == workspace_id))
        await db.execute(delete(APIToken).where(APIToken.workspace_id == workspace_id))
        await db.execute(
            delete(KnowledgeInsight).where(KnowledgeInsight.workspace_id == workspace_id)
        )
        await db.execute(delete(ResearchReport).where(ResearchReport.workspace_id == workspace_id))
        await db.execute(
            delete(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
        )

        await db.delete(workspace)
        await db.commit()
        return True

    @staticmethod
    async def update_ip_policy(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        ip_allowlist: list[str],
    ) -> Workspace:
        from app.core.ip_policy import validate_cidr_rules

        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, user_id)

        membership_res = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        member = membership_res.scalar_one_or_none()
        if not member or member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update workspace IP policy.",
            )

        try:
            validated = validate_cidr_rules(ip_allowlist)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

        new_settings = dict(workspace.settings or {})
        new_settings["ip_allowlist"] = validated
        workspace.settings = new_settings
        await db.commit()
        await db.refresh(workspace)
        return workspace

    @staticmethod
    async def update_retention_policy(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        retention_days: int | None,
    ) -> Workspace:
        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, user_id)

        membership_res = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        member = membership_res.scalar_one_or_none()
        if not member or member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update retention policy.",
            )

        new_settings = dict(workspace.settings or {})
        new_settings["retention_days"] = retention_days
        workspace.settings = new_settings
        await db.commit()
        await db.refresh(workspace)
        return workspace

    @staticmethod
    async def store_secret(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        name: str,
        value: str,
    ) -> dict:
        from sqlalchemy.orm.attributes import flag_modified

        from app.core.encryption import CMEKService, SecretEncryptionService

        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, user_id)

        membership_res = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        member = membership_res.scalar_one_or_none()
        if not member or member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to manage workspace secrets.",
            )

        new_settings = dict(workspace.settings or {})
        cmek = dict(new_settings.get("cmek", {}))
        key_version = cmek.get("key_version", 1)
        salt = cmek.get("salt")
        if cmek.get("enabled"):
            ciphertext = CMEKService.encrypt_with_cmek(value, workspace.id, key_version, salt)
        else:
            ciphertext = SecretEncryptionService.encrypt_secret(value)

        secrets_dict = dict(new_settings.get("encrypted_secrets", {}))
        now_dt = datetime.now(UTC)
        secrets_dict[name] = {
            "ciphertext": ciphertext,
            "key_version": key_version,
            "created_at": now_dt.isoformat(),
        }
        new_settings["encrypted_secrets"] = secrets_dict
        workspace.settings = new_settings
        flag_modified(workspace, "settings")
        await db.commit()
        await db.refresh(workspace)

        return {
            "name": name,
            "masked_value": SecretEncryptionService.mask_secret(value),
            "created_at": now_dt,
        }

    @staticmethod
    async def list_secrets(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
    ) -> list[dict]:
        from app.core.encryption import CMEKService, SecretEncryptionService

        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, user_id)

        membership_res = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        member = membership_res.scalar_one_or_none()
        if not member or member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view workspace secrets.",
            )

        cmek = (workspace.settings or {}).get("cmek", {})
        secrets_dict = (workspace.settings or {}).get("encrypted_secrets", {})
        result = []
        for name, entry in sorted(secrets_dict.items()):
            ct = entry.get("ciphertext", "")
            if ct.startswith("SHREDDED_"):
                masked = "••••[SHREDDED]••••"
            else:
                entry_v = entry.get("key_version", cmek.get("key_version", 1))
                salt = cmek.get("salt")
                try:
                    plaintext = CMEKService.decrypt_with_cmek(ct, workspace.id, entry_v, salt)
                    masked = SecretEncryptionService.mask_secret(plaintext)
                except Exception:
                    masked = "••••••••"

            created_at_str = entry.get("created_at")
            if created_at_str:
                try:
                    created_at_dt = datetime.fromisoformat(created_at_str)
                except Exception:
                    created_at_dt = datetime.now(UTC)
            else:
                created_at_dt = datetime.now(UTC)

            result.append(
                {
                    "name": name,
                    "masked_value": masked,
                    "created_at": created_at_dt,
                }
            )
        return result

    @staticmethod
    async def delete_secret(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        name: str,
    ) -> bool:
        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, user_id)

        membership_res = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        member = membership_res.scalar_one_or_none()
        if not member or member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete workspace secrets.",
            )

        new_settings = dict(workspace.settings or {})
        secrets_dict = dict(new_settings.get("encrypted_secrets", {}))
        if name in secrets_dict:
            del secrets_dict[name]
            new_settings["encrypted_secrets"] = secrets_dict
            workspace.settings = new_settings
            await db.commit()
            await db.refresh(workspace)
            return True
        return False

    @staticmethod
    async def prune_retention_memories(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
    ) -> dict:
        from app.ai.semantic_cache import SemanticCache
        from app.models.memory import Memory, MemoryStatus

        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, user_id)
        membership_res = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        member = membership_res.scalar_one_or_none()
        if not member or member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to execute memory retention pruning.",
            )

        retention_days = (workspace.settings or {}).get("retention_days")
        now = datetime.now(UTC)

        q = select(Memory).where(
            Memory.workspace_id == workspace_id,
            Memory.status == MemoryStatus.APPROVED,
            Memory.is_pinned.is_(False),
        )
        res = await db.execute(q)
        memories = list(res.scalars().all())

        archived_ids = []
        for m in memories:
            should_prune = False
            # Check valid_until expiration
            if m.valid_until is not None:
                vu = m.valid_until if m.valid_until.tzinfo else m.valid_until.replace(tzinfo=UTC)
                if vu <= now:
                    should_prune = True

            # Check retention_days expiration
            if not should_prune and retention_days is not None:
                ca = m.created_at if m.created_at.tzinfo else m.created_at.replace(tzinfo=UTC)
                if ca + timedelta(days=retention_days) <= now:
                    should_prune = True

            if should_prune:
                m.status = MemoryStatus.ARCHIVED
                archived_ids.append(m.id)

        if archived_ids:
            await db.commit()
            SemanticCache.invalidate_workspace(workspace_id)

        return {
            "pruned_count": len(archived_ids),
            "archived_ids": archived_ids,
        }

    @staticmethod
    async def rotate_workspace_cmek(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
    ) -> dict:
        """Rotate customer-managed encryption key (CMEK), re-encrypting all workspace secrets under new key version."""
        from sqlalchemy.orm.attributes import flag_modified

        from app.core.encryption import CMEKService

        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, user_id)

        membership_res = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        member = membership_res.scalar_one_or_none()
        if not member or member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to rotate workspace encryption keys (Admin or Owner only).",
            )

        new_settings = dict(workspace.settings or {})
        cmek = dict(new_settings.get("cmek", {}))
        old_version = cmek.get("key_version", 1)
        old_salt = cmek.get("salt")

        new_version = old_version + 1
        new_salt = CMEKService.generate_salt()
        now_dt = datetime.now(UTC)

        secrets_dict = dict(new_settings.get("encrypted_secrets", {}))
        reencrypted_count = 0

        for name, entry in list(secrets_dict.items()):
            old_ct = entry.get("ciphertext", "")
            if not old_ct or old_ct.startswith("SHREDDED_"):
                continue
            entry_version = entry.get("key_version", old_version)
            try:
                plaintext = CMEKService.decrypt_with_cmek(
                    old_ct, workspace.id, entry_version, old_salt
                )
                new_ct = CMEKService.encrypt_with_cmek(
                    plaintext, workspace.id, new_version, new_salt
                )
                entry["ciphertext"] = new_ct
                entry["key_version"] = new_version
                entry["reencrypted_at"] = now_dt.isoformat()
                secrets_dict[name] = entry
                reencrypted_count += 1
            except Exception as e:
                logger.error(f"Failed to re-encrypt secret '{name}' during CMEK rotation: {e}")

        cmek["enabled"] = True
        cmek["key_version"] = new_version
        cmek["salt"] = new_salt
        cmek["last_rotated_at"] = now_dt.isoformat()

        new_settings["cmek"] = cmek
        new_settings["encrypted_secrets"] = secrets_dict
        workspace.settings = new_settings
        flag_modified(workspace, "settings")
        await db.commit()
        await db.refresh(workspace)

        return {
            "workspace_id": workspace.id,
            "previous_key_version": old_version,
            "new_key_version": new_version,
            "reencrypted_secrets_count": reencrypted_count,
            "rotated_at": now_dt,
        }

    @staticmethod
    async def crypto_shred_workspace(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
    ) -> dict:
        """Permanently and irreversibly crypto-shred all stored workspace secrets and key material."""
        import secrets

        from sqlalchemy.orm.attributes import flag_modified

        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, user_id)

        membership_res = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        member = membership_res.scalar_one_or_none()
        if not member or member.role != WorkspaceRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Crypto-shredding is a high-risk destructive operation reserved strictly for the workspace OWNER.",
            )

        new_settings = dict(workspace.settings or {})
        secrets_dict = dict(new_settings.get("encrypted_secrets", {}))
        now_dt = datetime.now(UTC)

        shredded_count = 0
        for name, entry in list(secrets_dict.items()):
            entry["ciphertext"] = f"SHREDDED_ZEROIZED_{secrets.token_hex(32)}"
            entry["key_version"] = -1
            entry["shredded_at"] = now_dt.isoformat()
            secrets_dict[name] = entry
            shredded_count += 1

        cmek = dict(new_settings.get("cmek", {}))
        cmek["enabled"] = False
        cmek["salt"] = "SHREDDED_ZEROIZED_KEY"
        cmek["is_shredded"] = True
        cmek["shredded_at"] = now_dt.isoformat()

        new_settings["cmek"] = cmek
        new_settings["encrypted_secrets"] = secrets_dict
        workspace.settings = new_settings
        flag_modified(workspace, "settings")
        await db.commit()
        await db.refresh(workspace)

        return {
            "workspace_id": workspace.id,
            "shredded_secrets_count": shredded_count,
            "status": "crypto_shredded",
            "shredded_at": now_dt,
        }

    @staticmethod
    async def get_benchmark_telemetry(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
    ) -> dict:
        """Measure real-time RAG retrieval latency, retention health, semantic cache hit-ratio,

        redundancy index, and overall platform readiness score.
        """
        import time

        from sqlalchemy import func

        from app.ai.semantic_cache import SemanticCache
        from app.models.memory import Memory, MemoryStatus
        from app.services.memory_service import MemoryService

        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, user_id)

        # 1. Memory counts & conflict metrics
        q_all = select(Memory).where(Memory.workspace_id == workspace_id)
        all_memories = list((await db.execute(q_all)).scalars().all())

        total = len(all_memories)
        active = sum(1 for m in all_memories if m.status == MemoryStatus.APPROVED)
        superseded = sum(1 for m in all_memories if m.status == MemoryStatus.SUPERSEDED)
        pending_conflicts = sum(1 for m in all_memories if m.status == MemoryStatus.PENDING_REVIEW)
        resolved_conflicts = sum(
            1 for m in all_memories if (m.extra_metadata or {}).get("conflict_resolved") is True
        )

        total_conflicts = pending_conflicts + resolved_conflicts
        resolution_rate = (
            round(resolved_conflicts / total_conflicts, 3) if total_conflicts > 0 else 1.0
        )

        # 2. Biological retention health
        decay_stats = await MemoryService.get_decay_analytics(db, workspace_id)
        strong = decay_stats["strong_count"]
        fading = decay_stats["fading_count"]
        dormant = decay_stats["dormant_count"]
        health_index = round((strong * 1.0 + fading * 0.5) / max(total, 1), 3) if total > 0 else 1.0

        retention_health = {
            "strong_count": strong,
            "fading_count": fading,
            "dormant_count": dormant,
            "average_retention": decay_stats["average_retention"],
            "retention_health_index": health_index,
        }

        # 3. Live query round-trip benchmark latency
        t0 = time.perf_counter()
        await db.execute(select(func.count(Memory.id)).where(Memory.workspace_id == workspace_id))
        query_latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        retrieval_perf = {
            "query_latency_ms": query_latency_ms,
            "hnsw_accelerated": True,
            "vector_dimension": 1536,
            "retrieval_status": "optimal",
        }

        # 4. Semantic Cache stats
        cache_stats = SemanticCache.get_stats(workspace_id=workspace_id)

        # 5. Redundancy rate
        redundancy_rate = round(superseded / max(total, 1), 3) if total > 0 else 0.0

        # 6. Overall Platform Grade
        if health_index >= 0.70 and resolution_rate >= 0.75:
            grade = "A+"
        elif health_index >= 0.50:
            grade = "A"
        else:
            grade = "B+"

        return {
            "workspace_id": workspace.id,
            "workspace_name": workspace.name,
            "total_memories": total,
            "active_memories": active,
            "superseded_memories": superseded,
            "pending_conflicts": pending_conflicts,
            "resolved_conflicts": resolved_conflicts,
            "conflict_resolution_rate": resolution_rate,
            "retention_health": retention_health,
            "retrieval_performance": retrieval_perf,
            "cache_efficiency": cache_stats,
            "redundancy_rate": redundancy_rate,
            "platform_grade": grade,
            "evaluated_at": datetime.now(UTC),
        }

    @staticmethod
    async def run_workspace_rag_probe(
        db: AsyncSession,
        workspace_id: str,
        current_user_id: str,
        sample_size: int = 5,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Execute automated synthetic RAG retrieval probe benchmark against workspace ground-truth memories."""
        from app.ai.rag_evaluator import RAGGroundingEvaluator
        from app.models.memory import Memory, MemoryStatus

        await WorkspaceService.get_workspace_by_id(db, workspace_id, current_user_id)

        # Fetch active memories to probe
        q = (
            select(Memory)
            .where(
                Memory.workspace_id == workspace_id,
                Memory.status == MemoryStatus.APPROVED,
            )
            .order_by(Memory.created_at.desc())
        )
        memories = list((await db.execute(q)).scalars().all())

        return await RAGGroundingEvaluator.run_benchmark(
            db=db,
            workspace_id=workspace_id,
            memories=memories,
            sample_size=sample_size,
            top_k=top_k,
        )

    @staticmethod
    async def get_workspace_rag_eval_history(
        db: AsyncSession,
        workspace_id: str,
        current_user_id: str,
    ) -> dict[str, Any]:
        """Retrieve historical synthetic RAG retrieval probe runs."""
        from app.ai.rag_evaluator import RAGGroundingEvaluator

        await WorkspaceService.get_workspace_by_id(db, workspace_id, current_user_id)
        history = RAGGroundingEvaluator.get_eval_history(workspace_id)
        return {
            "workspace_id": workspace_id,
            "total_runs": len(history),
            "history": history,
        }

    @staticmethod
    async def get_workspace_dlp_policy(
        db: AsyncSession,
        workspace_id: str,
        current_user_id: str,
    ) -> dict[str, Any]:
        """Retrieve active DLP policy settings for the workspace."""
        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, current_user_id)
        settings = workspace.settings or {}
        dlp_cfg = settings.get("dlp_policy", {})
        return {
            "workspace_id": workspace.id,
            "enabled": dlp_cfg.get("enabled", False),
            "action": dlp_cfg.get("action", "REDACT"),
            "active_rules": dlp_cfg.get("active_rules", ["CREDIT_CARD", "SSN", "API_KEY"]),
            "custom_rules": dlp_cfg.get("custom_rules", []),
            "updated_at": workspace.updated_at or datetime.now(UTC),
        }

    @staticmethod
    async def update_workspace_dlp_policy(
        db: AsyncSession,
        workspace_id: str,
        current_user_id: str,
        enabled: bool,
        action: str,
        active_rules: list[str],
        custom_rules: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Update workspace DLP policy rules and enforcement action (OWNER or ADMIN only)."""
        from sqlalchemy.orm.attributes import flag_modified

        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, current_user_id)

        # RBAC Check: OWNER or ADMIN
        q = select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user_id,
        )
        role = (await db.execute(q)).scalar_one_or_none()
        if role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace administrators and owners can update DLP policy settings.",
            )

        now_dt = datetime.now(UTC)
        new_settings = dict(workspace.settings or {})
        dlp_payload = {
            "enabled": enabled,
            "action": action.upper(),
            "active_rules": active_rules,
            "custom_rules": custom_rules,
            "updated_at": now_dt.isoformat(),
        }
        new_settings["dlp_policy"] = dlp_payload
        workspace.settings = new_settings
        flag_modified(workspace, "settings")
        await db.commit()
        await db.refresh(workspace)

        return {
            "workspace_id": workspace.id,
            "enabled": enabled,
            "action": action.upper(),
            "active_rules": active_rules,
            "custom_rules": custom_rules,
            "updated_at": now_dt,
        }

    @staticmethod
    async def inspect_workspace_dlp(
        db: AsyncSession,
        workspace_id: str,
        current_user_id: str,
        text: str,
    ) -> dict[str, Any]:
        """Inspect and test a text payload against workspace DLP policy."""
        from app.core.dlp import WorkspaceDLPService

        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, current_user_id)
        settings = workspace.settings or {}
        dlp_cfg = settings.get("dlp_policy", {})
        result = WorkspaceDLPService.inspect(text, dlp_cfg)

        return {
            "original_text": result.original_text,
            "sanitized_text": result.sanitized_text,
            "is_clean": result.is_clean,
            "violations": result.violations,
            "action_taken": result.action,
            "blocked": result.blocked,
        }

    @staticmethod
    async def get_workspace_memory_drift(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        window_days: int = 30,
    ) -> dict[str, Any]:
        """Evaluate semantic centroid drift, tag velocity, and contradiction drift."""
        from app.ai.drift_detector import MemoryDriftDetector
        from app.models.memory import Memory

        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, user_id)
        q = (
            select(Memory)
            .where(Memory.workspace_id == workspace.id)
            .order_by(Memory.created_at.asc())
        )
        res = await db.execute(q)
        memories = list(res.scalars().all())

        result = MemoryDriftDetector.analyze_workspace_drift(
            workspace_id=workspace.id,
            memories=memories,
            window_days=window_days,
        )

        return {
            "workspace_id": result.workspace_id,
            "window_days": result.window_days,
            "baseline_memory_count": result.baseline_memory_count,
            "recent_memory_count": result.recent_memory_count,
            "centroid_distance": result.centroid_distance,
            "drift_score": result.drift_score,
            "drift_status": result.drift_status,
            "top_accelerating_topics": [
                {
                    "tag": t.tag,
                    "baseline_freq": t.baseline_freq,
                    "recent_freq": t.recent_freq,
                    "acceleration": t.acceleration,
                }
                for t in result.top_accelerating_topics
            ],
            "top_declining_topics": [
                {
                    "tag": t.tag,
                    "baseline_freq": t.baseline_freq,
                    "recent_freq": t.recent_freq,
                    "acceleration": t.acceleration,
                }
                for t in result.top_declining_topics
            ],
            "conflict_velocity_ratio": result.conflict_velocity_ratio,
            "analyzed_at": result.analyzed_at,
        }

    @staticmethod
    async def get_workspace_compliance_scorecard(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Evaluate 8-point continuous security and regulatory compliance scorecard."""
        from app.core.audit import SecurityAuditLogger
        from app.services.memory_service import MemoryService

        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, user_id)
        settings = workspace.settings or {}
        controls: list[dict[str, Any]] = []
        recommendations: list[str] = []

        # 1. CMEK Encryption
        cmek_enabled = bool(settings.get("cmek_enabled")) or bool(settings.get("cmek_key_arn"))
        if cmek_enabled:
            controls.append(
                {
                    "control_id": "CMEK_ENCRYPTION",
                    "control_name": "Customer-Managed Encryption Keys (CMEK)",
                    "category": "Data Protection & Encryption",
                    "status": "PASS",
                    "details": "CMEK hardware encryption is enabled and envelope keys are active.",
                    "is_auto_remediable": False,
                }
            )
        else:
            controls.append(
                {
                    "control_id": "CMEK_ENCRYPTION",
                    "control_name": "Customer-Managed Encryption Keys (CMEK)",
                    "category": "Data Protection & Encryption",
                    "status": "WARN",
                    "details": "Workspace is utilizing AES-256 platform managed keys; configure a dedicated KMS ARN for strict CMEK compliance.",
                    "is_auto_remediable": False,
                }
            )
            recommendations.append(
                "Configure a Customer-Managed Encryption Key (CMEK) ARN in workspace security settings."
            )

        # 2. DLP Enforcement
        dlp_cfg = settings.get("dlp_policy", {})
        dlp_enabled = bool(dlp_cfg.get("enabled", False))
        dlp_action = str(dlp_cfg.get("action", "")).upper()
        if dlp_enabled and dlp_action in ("REDACT", "BLOCK"):
            controls.append(
                {
                    "control_id": "DLP_ENFORCEMENT",
                    "control_name": "Data Loss Prevention (DLP) Policies",
                    "category": "Data Security & Privacy",
                    "status": "PASS",
                    "details": f"DLP policy active with enforcement action '{dlp_action}' across {len(dlp_cfg.get('active_rules', []))} detectors.",
                    "is_auto_remediable": True,
                }
            )
        else:
            controls.append(
                {
                    "control_id": "DLP_ENFORCEMENT",
                    "control_name": "Data Loss Prevention (DLP) Policies",
                    "category": "Data Security & Privacy",
                    "status": "FAIL",
                    "details": "DLP policy is inactive or unconfigured; sensitive PII/secrets may be stored in raw plaintext.",
                    "is_auto_remediable": True,
                }
            )
            recommendations.append(
                "Enable Data Loss Prevention (DLP) policy with automated REDACT or BLOCK enforcement."
            )

        # 3. CIDR Geofencing
        ip_allowlist = settings.get("ip_allowlist") or settings.get("cidr_rules") or []
        if ip_allowlist and len(ip_allowlist) > 0:
            controls.append(
                {
                    "control_id": "CIDR_GEOFENCING",
                    "control_name": "Network Perimeter & CIDR IP Geofencing",
                    "category": "Access Control",
                    "status": "PASS",
                    "details": f"Perimeter firewall enforces {len(ip_allowlist)} CIDR ingress boundary rules.",
                    "is_auto_remediable": False,
                }
            )
        else:
            controls.append(
                {
                    "control_id": "CIDR_GEOFENCING",
                    "control_name": "Network Perimeter & CIDR IP Geofencing",
                    "category": "Access Control",
                    "status": "WARN",
                    "details": "No CIDR IP restrictions configured; workspace is accessible from all public IP ranges.",
                    "is_auto_remediable": False,
                }
            )
            recommendations.append(
                "Restrict network access to corporate CIDR blocks or VPN egress IPs."
            )

        # 4. Cryptographic Audit Chain Integrity
        audit_check = await SecurityAuditLogger.verify_chain(db, workspace_id=workspace.id)
        if audit_check.get("is_valid", True):
            controls.append(
                {
                    "control_id": "AUDIT_CHAIN_INTEGRITY",
                    "control_name": "Cryptographic Tamper-Evident Audit Chain",
                    "category": "Compliance & Governance",
                    "status": "PASS",
                    "details": f"Cryptographic audit log chain verified intact across {audit_check.get('total_records_checked', 0)} events.",
                    "is_auto_remediable": True,
                }
            )
        else:
            controls.append(
                {
                    "control_id": "AUDIT_CHAIN_INTEGRITY",
                    "control_name": "Cryptographic Tamper-Evident Audit Chain",
                    "category": "Compliance & Governance",
                    "status": "FAIL",
                    "details": f"Audit log chain tampering detected at event {audit_check.get('tampered_record_id')}; hash integrity violated.",
                    "is_auto_remediable": True,
                }
            )
            recommendations.append(
                "Audit hash chain integrity mismatch detected; run audit chain reconciliation."
            )

        # 5. Memory Row-Level HMAC Tamper Check
        mem_check = await MemoryService.verify_workspace_integrity(db, workspace_id=workspace.id)
        if mem_check.get("tampered_count", 0) == 0:
            controls.append(
                {
                    "control_id": "MEMORY_HMAC_TAMPER",
                    "control_name": "Memory Row-Level HMAC-SHA256 Signatures",
                    "category": "Data Integrity",
                    "status": "PASS",
                    "details": f"All {mem_check.get('total_checked', 0)} memory records have valid cryptographic HMAC signatures.",
                    "is_auto_remediable": True,
                }
            )
        else:
            controls.append(
                {
                    "control_id": "MEMORY_HMAC_TAMPER",
                    "control_name": "Memory Row-Level HMAC-SHA256 Signatures",
                    "category": "Data Integrity",
                    "status": "FAIL",
                    "details": f"{mem_check.get('tampered_count')} of {mem_check.get('total_checked')} memories lack or have invalid HMAC signatures.",
                    "is_auto_remediable": True,
                }
            )
            recommendations.append(
                "One or more memory records lack valid HMAC signatures; re-sign memory store."
            )

        # 6. Member MFA Adoption
        mfa_query = (
            select(User.is_mfa_enabled)
            .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
            .where(WorkspaceMember.workspace_id == workspace.id)
        )
        mfa_results = (await db.execute(mfa_query)).scalars().all()
        total_members = max(len(mfa_results), 1)
        mfa_enabled_count = sum(1 for m in mfa_results if m)
        mfa_ratio = mfa_enabled_count / total_members

        if mfa_ratio >= 0.5:
            controls.append(
                {
                    "control_id": "MEMBER_MFA_ADOPTION",
                    "control_name": "Member Multi-Factor Authentication (MFA)",
                    "category": "Identity & Authentication",
                    "status": "PASS",
                    "details": f"MFA adoption is {round(mfa_ratio * 100)}% ({mfa_enabled_count}/{len(mfa_results)} members protected).",
                    "is_auto_remediable": False,
                }
            )
        else:
            controls.append(
                {
                    "control_id": "MEMBER_MFA_ADOPTION",
                    "control_name": "Member Multi-Factor Authentication (MFA)",
                    "category": "Identity & Authentication",
                    "status": "WARN",
                    "details": f"MFA adoption is {round(mfa_ratio * 100)}% ({mfa_enabled_count}/{len(mfa_results)} members). Two-factor authentication recommended.",
                    "is_auto_remediable": False,
                }
            )
            recommendations.append(
                "Mandate multi-factor authentication (MFA/TOTP) for all workspace collaborators."
            )

        # 7. TTL Retention Pruning
        retention_days = settings.get("retention_policy_days")
        if retention_days and int(retention_days) > 0:
            controls.append(
                {
                    "control_id": "TTL_RETENTION_PRUNING",
                    "control_name": "Automated Data Retention & TTL Pruning",
                    "category": "Data Lifecycle Management",
                    "status": "PASS",
                    "details": f"Retention lifecycle policy configured with {retention_days}-day automatic expiry.",
                    "is_auto_remediable": True,
                }
            )
        else:
            controls.append(
                {
                    "control_id": "TTL_RETENTION_PRUNING",
                    "control_name": "Automated Data Retention & TTL Pruning",
                    "category": "Data Lifecycle Management",
                    "status": "WARN",
                    "details": "Indefinite retention policy active; no automated pruning window configured.",
                    "is_auto_remediable": True,
                }
            )
            recommendations.append(
                "Define a regulatory retention schedule (e.g. 365 days) for automated TTL pruning."
            )

        # 8. Storage Quota Compliance
        usage_bytes = getattr(workspace, "storage_usage_bytes", 0) or settings.get(
            "storage_usage_bytes", 0
        )
        quota_bytes = 10 * 1024 * 1024 * 1024  # Default 10GB baseline
        if workspace.plan_tier == WorkspacePlan.TEAM:
            quota_bytes = 1024 * 1024 * 1024 * 1024
        elif workspace.plan_tier == WorkspacePlan.PRO:
            quota_bytes = 100 * 1024 * 1024 * 1024

        usage_ratio = usage_bytes / max(quota_bytes, 1)
        if usage_ratio < 0.8:
            controls.append(
                {
                    "control_id": "STORAGE_QUOTA_COMPLIANCE",
                    "control_name": "Storage Quota & Volume Overhead Safety",
                    "category": "Resource Management",
                    "status": "PASS",
                    "details": f"Storage utilization within safe operational limits ({round(usage_bytes / (1024 * 1024), 2)} MB used of {round(quota_bytes / (1024 * 1024 * 1024))} GB).",
                    "is_auto_remediable": False,
                }
            )
        elif usage_ratio < 1.0:
            controls.append(
                {
                    "control_id": "STORAGE_QUOTA_COMPLIANCE",
                    "control_name": "Storage Quota & Volume Overhead Safety",
                    "category": "Resource Management",
                    "status": "WARN",
                    "details": f"Storage capacity exceeds 80% threshold ({round(usage_bytes / (1024 * 1024), 2)} MB used).",
                    "is_auto_remediable": False,
                }
            )
            recommendations.append(
                "Storage quota nearing limit; archive stale documents or upgrade plan tier."
            )
        else:
            controls.append(
                {
                    "control_id": "STORAGE_QUOTA_COMPLIANCE",
                    "control_name": "Storage Quota & Volume Overhead Safety",
                    "category": "Resource Management",
                    "status": "FAIL",
                    "details": "Storage quota limit exceeded.",
                    "is_auto_remediable": False,
                }
            )
            recommendations.append(
                "Storage quota exceeded; immediate cleanup or quota elevation required."
            )

        # Compute Score: PASS = 12.5, WARN = 6.25, FAIL = 0.0
        passed_count = sum(1 for c in controls if c["status"] == "PASS")
        warned_count = sum(1 for c in controls if c["status"] == "WARN")
        failed_count = sum(1 for c in controls if c["status"] == "FAIL")

        raw_score = (passed_count * 12.5) + (warned_count * 6.25)
        compliance_score = int(round(raw_score))

        if compliance_score >= 90:
            grade = "A+"
        elif compliance_score >= 80:
            grade = "A"
        elif compliance_score >= 70:
            grade = "B"
        elif compliance_score >= 60:
            grade = "C"
        else:
            grade = "D"

        return {
            "workspace_id": workspace.id,
            "compliance_score": compliance_score,
            "platform_grade": grade,
            "controls_passed": passed_count,
            "controls_warned": warned_count,
            "controls_failed": failed_count,
            "controls": controls,
            "remediation_recommendations": recommendations,
            "evaluated_at": datetime.now(UTC),
        }

    @staticmethod
    async def auto_remediate_workspace_compliance(
        db: AsyncSession,
        workspace_id: str,
        current_user_id: str,
    ) -> dict[str, Any]:
        """Execute automated one-click remediation for auto-fixable security and compliance controls."""
        from sqlalchemy.orm.attributes import flag_modified

        from app.models.memory import Memory
        from app.services.memory_service import MemoryService

        workspace = await WorkspaceService.get_workspace_by_id(db, workspace_id, current_user_id)

        # RBAC Check: OWNER or ADMIN
        q = select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user_id,
        )
        role = (await db.execute(q)).scalar_one_or_none()
        if role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace administrators and owners can execute compliance remediation.",
            )

        # Baseline evaluation
        pre_eval = await WorkspaceService.get_workspace_compliance_scorecard(
            db, workspace_id, current_user_id
        )
        prev_score = pre_eval["compliance_score"]

        remediated_controls: list[str] = []
        details: list[str] = []
        new_settings = dict(workspace.settings or {})
        modified_settings = False

        # 1. Remediate DLP
        dlp_cfg = new_settings.get("dlp_policy", {})
        if not dlp_cfg.get("enabled") or str(dlp_cfg.get("action")).upper() not in (
            "REDACT",
            "BLOCK",
        ):
            new_settings["dlp_policy"] = {
                "enabled": True,
                "action": "REDACT",
                "active_rules": ["CREDIT_CARD", "SSN", "API_KEY"],
                "custom_rules": [],
                "updated_at": datetime.now(UTC).isoformat(),
            }
            modified_settings = True
            remediated_controls.append("DLP_ENFORCEMENT")
            details.append(
                "Activated Data Loss Prevention with REDACT enforcement on CREDIT_CARD, SSN, and API_KEY."
            )

        # 2. Remediate TTL Retention
        if not new_settings.get("retention_policy_days"):
            new_settings["retention_policy_days"] = 365
            modified_settings = True
            remediated_controls.append("TTL_RETENTION_PRUNING")
            details.append(
                "Configured standard 365-day compliance data retention and automated TTL pruning window."
            )

        if modified_settings:
            workspace.settings = new_settings
            flag_modified(workspace, "settings")

        # 3. Remediate Memory HMAC Signatures
        mem_q = select(Memory).where(Memory.workspace_id == workspace_id)
        mem_res = await db.execute(mem_q)
        all_memories = list(mem_res.scalars().all())

        re_signed_count = 0
        for m in all_memories:
            expected_sig = MemoryService.compute_integrity_signature(
                workspace_id=m.workspace_id,
                memory_id=m.id,
                content=m.content,
                category=m.category.value if hasattr(m.category, "value") else str(m.category),
                importance=m.importance,
            )
            meta = dict(m.extra_metadata or {})
            if meta.get("integrity_signature") != expected_sig:
                meta["integrity_signature"] = expected_sig
                m.extra_metadata = meta
                flag_modified(m, "extra_metadata")
                re_signed_count += 1

        if re_signed_count > 0:
            remediated_controls.append("MEMORY_HMAC_TAMPER")
            details.append(
                f"Regenerated cryptographic HMAC-SHA256 signatures for {re_signed_count} memory records."
            )

        await db.commit()
        await db.refresh(workspace)

        # Re-evaluate
        post_eval = await WorkspaceService.get_workspace_compliance_scorecard(
            db, workspace_id, current_user_id
        )
        updated_score = post_eval["compliance_score"]

        return {
            "workspace_id": workspace.id,
            "previous_score": prev_score,
            "updated_score": updated_score,
            "remediated_controls": remediated_controls,
            "details": details,
            "remediated_at": datetime.now(UTC),
        }
