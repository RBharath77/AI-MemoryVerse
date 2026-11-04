
from fastapi import HTTPException, status
from sqlalchemy import String, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import (
    Memory,
    MemoryCategory,
    MemoryStatus,
    MemoryVersion,
)
from app.schemas.memory import MemoryCreate, MemoryUpdate


class MemoryService:
    @staticmethod
    async def create_memory(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        data: MemoryCreate,
    ) -> Memory:
        memory = Memory(
            workspace_id=workspace_id,
            user_id=user_id,
            content=data.content,
            category=data.category,
            status=MemoryStatus.APPROVED,
            importance=data.importance,
            confidence=data.confidence,
            is_pinned=data.is_pinned,
            source_type=data.source_type,
            source_id=data.source_id,
            tags=data.tags or [],
            extra_metadata=data.extra_metadata or {},
        )
        db.add(memory)
        await db.flush()

        # Create initial version
        version = MemoryVersion(
            memory_id=memory.id,
            version_number=1,
            content=memory.content,
            category=memory.category.value,
            changed_by_user_id=user_id,
            change_reason="Initial creation",
        )
        db.add(version)
        await db.commit()
        await db.refresh(memory)
        return memory

    @staticmethod
    async def list_memories(
        db: AsyncSession,
        workspace_id: str,
        category: MemoryCategory | None = None,
        status: MemoryStatus | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Memory], int]:
        query = select(Memory).where(Memory.workspace_id == workspace_id)

        if category:
            query = query.where(Memory.category == category)
        if status:
            query = query.where(Memory.status == status)
        if search:
            query = query.where(
                or_(
                    Memory.content.ilike(f"%{search}%"),
                    Memory.tags.cast(String).ilike(f"%{search}%"),
                )
            )

        # Count total
        count_query = select(Memory.id).where(Memory.workspace_id == workspace_id)
        if category:
            count_query = count_query.where(Memory.category == category)
        if status:
            count_query = count_query.where(Memory.status == status)
        if search:
            count_query = count_query.where(
                or_(
                    Memory.content.ilike(f"%{search}%"),
                    Memory.tags.cast(String).ilike(f"%{search}%"),
                )
            )

        total_res = await db.execute(count_query)
        total = len(total_res.scalars().all())

        # Sort pinned first, then newest
        query = query.order_by(
            desc(Memory.is_pinned),
            desc(Memory.created_at),
        ).limit(limit).offset(offset)

        result = await db.execute(query)
        return list(result.scalars().all()), total

    @staticmethod
    async def get_memory(
        db: AsyncSession,
        workspace_id: str,
        memory_id: str,
    ) -> Memory:
        query = select(Memory).where(
            Memory.id == memory_id,
            Memory.workspace_id == workspace_id,
        )
        result = await db.execute(query)
        memory = result.scalar_one_or_none()
        if not memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found or unauthorized access.",
            )
        return memory

    @staticmethod
    async def update_memory(
        db: AsyncSession,
        workspace_id: str,
        memory_id: str,
        user_id: str,
        data: MemoryUpdate,
    ) -> Memory:
        memory = await MemoryService.get_memory(db, workspace_id, memory_id)

        # Check if content changed to create a version
        content_changed = data.content is not None and data.content != memory.content

        if content_changed:
            # Get latest version number
            version_query = (
                select(MemoryVersion)
                .where(MemoryVersion.memory_id == memory_id)
                .order_by(desc(MemoryVersion.version_number))
            )
            v_res = await db.execute(version_query)
            latest_v = v_res.scalars().first()
            next_v = (latest_v.version_number + 1) if latest_v else 2

            new_v = MemoryVersion(
                memory_id=memory.id,
                version_number=next_v,
                content=data.content or memory.content,
                category=(data.category or memory.category).value,
                changed_by_user_id=user_id,
                change_reason="User edit",
            )
            db.add(new_v)
            memory.content = data.content

        if data.category is not None:
            memory.category = data.category
        if data.importance is not None:
            memory.importance = data.importance
        if data.is_pinned is not None:
            memory.is_pinned = data.is_pinned
        if data.tags is not None:
            memory.tags = data.tags
        if data.extra_metadata is not None:
            memory.extra_metadata = data.extra_metadata

        await db.commit()
        await db.refresh(memory)
        return memory

    @staticmethod
    async def delete_memory(
        db: AsyncSession,
        workspace_id: str,
        memory_id: str,
    ) -> bool:
        memory = await MemoryService.get_memory(db, workspace_id, memory_id)
        await db.delete(memory)
        await db.commit()
        return True
