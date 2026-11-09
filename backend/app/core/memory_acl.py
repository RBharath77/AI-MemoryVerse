from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.memory import Memory
from app.models.workspace import WorkspaceMember, WorkspaceRole
from app.schemas.memory import MemoryAclResponse, MemoryAclUpdate

logger = logging.getLogger("memoryverse.memory_acl")


class MemoryAccessControlService:
    """
    Attribute-Based Access Control (ABAC) & Fine-Grained Dynamic ACL Service for Workspace Memories.
    Enforces granular visibility scopes:
      - 'workspace': open to all workspace members
      - 'restricted': explicitly permitted roles and user IDs
      - 'private': author and workspace owner only
    """

    @classmethod
    async def get_user_workspace_role(
        cls,
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
    ) -> WorkspaceRole | None:
        """Resolve workspace member role for user."""
        q = select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        return (await db.execute(q)).scalar_one_or_none()

    @classmethod
    def can_user_access_memory(
        cls,
        memory: Memory,
        user_id: str,
        user_role: WorkspaceRole | None = None,
        is_superuser: bool = False,
        action: str = "read",
    ) -> bool:
        """Evaluate if user_id with user_role has action ('read' or 'write') permission on memory."""
        if is_superuser:
            return True

        is_author = str(memory.user_id) == str(user_id)
        is_owner = user_role == WorkspaceRole.OWNER
        is_admin = user_role == WorkspaceRole.ADMIN

        # Author and Workspace Owner have complete access
        if is_author or is_owner:
            return True

        if action == "write":
            # Only author, owner, or admin can write
            return is_admin

        # Action: "read"
        acl = (memory.extra_metadata or {}).get("acl", {})
        visibility = acl.get("visibility", "workspace")

        if visibility == "workspace":
            return True

        if visibility == "private":
            # Only author or owner (handled above) can read private memories
            return False

        if visibility == "restricted":
            allowed_users = {str(uid) for uid in acl.get("allowed_user_ids", [])}
            if str(user_id) in allowed_users:
                return True

            if user_role is not None:
                allowed_roles = {r.lower() for r in acl.get("allowed_roles", [])}
                user_role_str = (
                    user_role.value.lower()
                    if hasattr(user_role, "value")
                    else str(user_role).lower()
                )
                if user_role_str in allowed_roles:
                    return True

            return False

        return True

    @classmethod
    def get_memory_acl_policy(
        cls,
        memory: Memory,
        user_id: str,
        user_role: WorkspaceRole | None = None,
        is_superuser: bool = False,
    ) -> MemoryAclResponse:
        """Retrieve the active ACL policy and caller permissions on a memory."""
        acl = (memory.extra_metadata or {}).get("acl", {})
        visibility = acl.get("visibility", "workspace")
        allowed_roles = list(acl.get("allowed_roles", []))
        allowed_users = list(acl.get("allowed_user_ids", []))

        can_read = cls.can_user_access_memory(
            memory=memory,
            user_id=user_id,
            user_role=user_role,
            is_superuser=is_superuser,
            action="read",
        )
        can_write = cls.can_user_access_memory(
            memory=memory,
            user_id=user_id,
            user_role=user_role,
            is_superuser=is_superuser,
            action="write",
        )

        return MemoryAclResponse(
            memory_id=memory.id,
            visibility=visibility,
            allowed_roles=allowed_roles,
            allowed_user_ids=allowed_users,
            can_read=can_read,
            can_write=can_write,
            updated_at=datetime.now(UTC),
        )

    @classmethod
    async def update_memory_acl_policy(
        cls,
        db: AsyncSession,
        memory: Memory,
        user_id: str,
        user_role: WorkspaceRole | None = None,
        update_data: MemoryAclUpdate | None = None,
        is_superuser: bool = False,
    ) -> MemoryAclResponse:
        """Update the ACL policy on a memory (author, owner, or admin only)."""
        if update_data is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Update data must be provided",
            )
        can_write = cls.can_user_access_memory(
            memory=memory,
            user_id=user_id,
            user_role=user_role,
            is_superuser=is_superuser,
            action="write",
        )
        if not can_write:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the memory author or workspace administrators can modify access control policies.",
            )

        meta = dict(memory.extra_metadata or {})
        meta["acl"] = {
            "visibility": update_data.visibility,
            "allowed_roles": update_data.allowed_roles,
            "allowed_user_ids": update_data.allowed_user_ids,
            "updated_at": datetime.now(UTC).isoformat(),
            "updated_by": user_id,
        }
        memory.extra_metadata = meta
        flag_modified(memory, "extra_metadata")

        await db.commit()
        await db.refresh(memory)

        # Invalidate semantic cache so restricted memory is not returned to unauthorized queries
        try:
            from app.ai.semantic_cache import SemanticCache

            SemanticCache.invalidate_dependencies(memory.workspace_id, [memory.id])
        except Exception as e:
            logger.warning("Cache invalidation error on ACL update: %s", e)

        return cls.get_memory_acl_policy(
            memory=memory,
            user_id=user_id,
            user_role=user_role,
            is_superuser=is_superuser,
        )
