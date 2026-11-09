from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.memory import Memory, MemoryStatus
from app.schemas.workspace import (
    TimelineDiffResponse,
    TimeTravelMemoryItem,
    TimeTravelSnapshotResponse,
)
from app.services.workspace_service import WorkspaceService

logger = logging.getLogger("memoryverse.timeline_service")


class TimelineService:
    """Historical timeline reconstruction and time-travel memory state diffing engine."""

    @staticmethod
    def _normalize_dt(dt: datetime | None) -> datetime:
        if dt is None:
            return datetime.now(UTC)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt

    @classmethod
    async def reconstruct_time_travel_snapshot(
        cls,
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        as_of: datetime,
    ) -> TimeTravelSnapshotResponse:
        """Reconstruct the exact set of active memories in a workspace as of an arbitrary historical timestamp."""
        # Multi-tenant verification
        await WorkspaceService.get_workspace_by_id(db, workspace_id, user_id)

        target_time = cls._normalize_dt(as_of)

        # 1. Fetch all memories for the workspace created on or before target_time
        q = (
            select(Memory)
            .options(selectinload(Memory.versions))
            .where(Memory.workspace_id == workspace_id)
            .order_by(Memory.created_at.asc())
        )
        res = await db.execute(q)
        all_memories = list(res.scalars().all())

        # Map memory IDs to created_at for supersession checking
        mem_created_map = {m.id: cls._normalize_dt(m.created_at) for m in all_memories}

        active_items: list[TimeTravelMemoryItem] = []
        category_counts: Counter[str] = Counter()

        for m in all_memories:
            m_created = cls._normalize_dt(m.created_at)
            # Memory didn't exist yet at target_time
            if m_created > target_time:
                continue

            # Check valid_until expiration
            if m.valid_until and cls._normalize_dt(m.valid_until) <= target_time:
                continue

            # Check supersession
            if m.superseded_by:
                superseding_time = mem_created_map.get(m.superseded_by)
                # If superseded before or at target_time, it was already superseded
                if superseding_time and superseding_time <= target_time:
                    continue

            # If status was REJECTED at creation, skip
            if m.status == MemoryStatus.REJECTED:
                continue

            # Reconstruct content from versions if available
            effective_content = m.content
            version_number = 1
            if m.versions:
                # Find latest version created on or before target_time
                valid_versions = [
                    v for v in m.versions if cls._normalize_dt(v.created_at) <= target_time
                ]
                if valid_versions:
                    latest_v = max(valid_versions, key=lambda v: v.version_number)
                    effective_content = latest_v.content
                    version_number = latest_v.version_number

            cat_str = m.category.value if hasattr(m.category, "value") else str(m.category)
            category_counts[cat_str] += 1

            active_items.append(
                TimeTravelMemoryItem(
                    id=m.id,
                    content=effective_content,
                    category=cat_str,
                    importance=m.importance,
                    created_at=m.created_at,
                    status=m.status.value if hasattr(m.status, "value") else str(m.status),
                    version_at_time=version_number,
                )
            )

        return TimeTravelSnapshotResponse(
            workspace_id=workspace_id,
            as_of=target_time,
            active_memory_count=len(active_items),
            category_breakdown=dict(category_counts),
            memories=active_items,
            reconstructed_at=datetime.now(UTC),
        )

    @classmethod
    async def compute_timeline_diff(
        cls,
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        timestamp_a: datetime,
        timestamp_b: datetime,
    ) -> TimelineDiffResponse:
        """Compute fine-grained structural delta between two arbitrary historical points in time."""
        t_a = cls._normalize_dt(timestamp_a)
        t_b = cls._normalize_dt(timestamp_b)

        if t_a > t_b:
            t_a, t_b = t_b, t_a

        snap_a = await cls.reconstruct_time_travel_snapshot(db, workspace_id, user_id, t_a)
        snap_b = await cls.reconstruct_time_travel_snapshot(db, workspace_id, user_id, t_b)

        map_a = {m.id: m for m in snap_a.memories}
        map_b = {m.id: m for m in snap_b.memories}

        added_ids = set(map_b.keys()) - set(map_a.keys())
        superseded_ids = set(map_a.keys()) - set(map_b.keys())
        common_ids = set(map_a.keys()) & set(map_b.keys())

        modified_ids = [m_id for m_id in common_ids if map_a[m_id].content != map_b[m_id].content]

        added_payloads: list[dict[str, Any]] = [
            {
                "id": m_id,
                "content": map_b[m_id].content,
                "category": map_b[m_id].category,
                "created_at": map_b[m_id].created_at.isoformat(),
            }
            for m_id in added_ids
        ]

        superseded_payloads: list[dict[str, Any]] = [
            {
                "id": m_id,
                "content": map_a[m_id].content,
                "category": map_a[m_id].category,
                "historical_created_at": map_a[m_id].created_at.isoformat(),
            }
            for m_id in superseded_ids
        ]

        net_change = len(map_b) - len(map_a)
        summary = (
            f"Timeline Delta ({t_a.strftime('%Y-%m-%d %H:%M')} to {t_b.strftime('%Y-%m-%d %H:%M')}): "
            f"+{len(added_ids)} added, -{len(superseded_ids)} superseded, {len(modified_ids)} modified. "
            f"Active memory pool changed from {len(map_a)} to {len(map_b)} (Net: {net_change:+d})."
        )

        return TimelineDiffResponse(
            workspace_id=workspace_id,
            timestamp_a=t_a,
            timestamp_b=t_b,
            memories_added_count=len(added_ids),
            memories_superseded_count=len(superseded_ids),
            memories_modified_count=len(modified_ids),
            net_change=net_change,
            added_memories=added_payloads,
            superseded_memories=superseded_payloads,
            diff_summary=summary,
            analyzed_at=datetime.now(UTC),
        )
