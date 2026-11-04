import uuid

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

        await db.delete(target)
        await db.commit()
        return True
