from __future__ import annotations

import logging
import math
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import SecurityAuditLogger
from app.models.graph import GraphRelationship
from app.models.memory import Memory, MemoryCategory, MemoryLink, MemoryStatus
from app.schemas.memory import (
    PrunableCandidate,
    SleepCycleExecutionRequest,
    SleepCycleExecutionResponse,
    SleepCycleSimulationRequest,
    SleepCycleSimulationResponse,
)

logger = logging.getLogger("memoryverse.sleep_pruner")


class MemorySleepPruner:
    """
    Cognitive Sleep Cycle Pruning & Context Compaction Optimizer.
    Simulates and executes biological synaptic pruning across workspace memories:
    identifies low-utility, dormant, and transient memories while rigorously
    protecting pinned and knowledge-graph-anchored assets.
    """

    @classmethod
    async def simulate_sleep_cycle(
        cls,
        db: AsyncSession,
        workspace_id: str,
        request: SleepCycleSimulationRequest,
    ) -> SleepCycleSimulationResponse:
        """
        Simulate sleep cycle pruning over workspace memories.
        Computes utility scores, checks graph connections and pin locks, and returns candidate preview.
        """
        now_dt = datetime.now(UTC)

        # 1. Fetch active memories
        mem_stmt = select(Memory).where(
            Memory.workspace_id == workspace_id,
            Memory.status.in_([MemoryStatus.APPROVED, MemoryStatus.PENDING_REVIEW]),
        )
        memories = list((await db.execute(mem_stmt)).scalars().all())

        # 2. Collect graph and link-anchored memory IDs if protection enabled
        connected_memory_ids: set[str] = set()
        if request.protect_graph_connected:
            link_stmt = select(MemoryLink.source_memory_id, MemoryLink.target_memory_id).where(
                MemoryLink.workspace_id == workspace_id
            )
            link_rows = (await db.execute(link_stmt)).all()
            for src_id, tgt_id in link_rows:
                connected_memory_ids.add(src_id)
                connected_memory_ids.add(tgt_id)

            rel_stmt = select(GraphRelationship.source_memory_id).where(
                GraphRelationship.workspace_id == workspace_id,
                GraphRelationship.source_memory_id.isnot(None),
            )
            rel_rows = (await db.execute(rel_stmt)).scalars().all()
            for sm_id in rel_rows:
                if sm_id:
                    connected_memory_ids.add(sm_id)

        candidates: list[PrunableCandidate] = []
        protected_count = 0
        total_estimated_tokens = 0

        for mem in memories:
            # Check pin protection
            if request.protect_pinned and mem.is_pinned:
                protected_count += 1
                continue

            # Check graph protection
            if request.protect_graph_connected and mem.id in connected_memory_ids:
                protected_count += 1
                continue

            # Check high importance protection
            if mem.importance >= 9:
                protected_count += 1
                continue

            created_time = mem.created_at or now_dt
            if created_time.tzinfo is None:
                created_time = created_time.replace(tzinfo=UTC)

            delta_days = max(0, (now_dt - created_time).days)

            # Ebbinghaus-derived utility function
            decay_factor = math.exp(-0.05 * delta_days)
            raw_utility = (mem.importance / 10.0) * decay_factor

            # Transient discount
            tags_lower = [t.lower() for t in (mem.tags or [])]
            if any(t in tags_lower for t in ["transient", "scratchpad", "temporary", "draft"]):
                raw_utility *= 0.5

            utility = round(raw_utility, 3)

            # Determine eligibility
            is_eligible = utility < request.utility_threshold and (
                delta_days >= request.inactivity_days or "transient" in tags_lower
            )

            if is_eligible:
                token_count = int(len(mem.content.split()) * 1.3)
                total_estimated_tokens += token_count
                snippet = mem.content.strip().replace("\n", " ")[:120]
                candidates.append(
                    PrunableCandidate(
                        memory_id=mem.id,
                        content_snippet=snippet,
                        importance=mem.importance,
                        calculated_utility=utility,
                        inactivity_days=delta_days,
                        reason=(
                            "Low utility score and elapsed inactivity days"
                            if "transient" not in tags_lower
                            else "Transient scratchpad tag with decayed utility"
                        ),
                    )
                )

                if len(candidates) >= request.max_candidates:
                    break

        return SleepCycleSimulationResponse(
            workspace_id=workspace_id,
            total_active_memories=len(memories),
            candidates_identified=len(candidates),
            estimated_token_savings=total_estimated_tokens,
            protected_count=protected_count,
            candidates=candidates,
            simulated_at=now_dt,
        )

    @classmethod
    async def execute_sleep_cycle(
        cls,
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        request: SleepCycleExecutionRequest,
    ) -> SleepCycleExecutionResponse:
        """
        Commit sleep cycle pruning or context compaction across candidate memories.
        """
        now_dt = datetime.now(UTC)

        # 1. Fetch candidate memories with tenancy check
        stmt = select(Memory).where(
            Memory.workspace_id == workspace_id,
            Memory.id.in_(request.candidate_memory_ids),
        )
        memories = list((await db.execute(stmt)).scalars().all())

        if not memories:
            return SleepCycleExecutionResponse(
                workspace_id=workspace_id,
                action_executed=request.action,
                processed_count=0,
                compacted_memory_id=None,
                executed_at=now_dt,
            )

        compacted_id: str | None = None

        if request.action == "COMPACT":
            # Combine individual memories into a single consolidated digest
            title = request.compaction_title or "Cognitive Sleep-Cycle Compacted Digest"
            snippets = [f"• {m.content.strip()}" for m in memories]
            compacted_content = (
                f"{title}\n\nSynthesized {len(memories)} dormant context items:\n"
                + "\n".join(snippets)
            )

            compacted_id = str(uuid.uuid4())
            compacted_mem = Memory(
                id=compacted_id,
                workspace_id=workspace_id,
                user_id=user_id,
                content=compacted_content,
                category=MemoryCategory.SEMANTIC,
                status=MemoryStatus.APPROVED,
                importance=7,
                confidence=0.95,
                is_pinned=False,
                tags=["sleep_cycle", "compacted_archive"],
                source_type="sleep_pruner",
                extra_metadata={
                    "is_compacted_digest": True,
                    "source_memory_ids": [m.id for m in memories],
                    "compacted_at": now_dt.isoformat(),
                },
            )
            db.add(compacted_mem)

            # Archive the component memories and point to compacted digest
            for m in memories:
                m.status = MemoryStatus.ARCHIVED
                m.superseded_by = compacted_id

        elif request.action == "SUPERSEDE":
            for m in memories:
                m.status = MemoryStatus.SUPERSEDED

        else:  # Default: ARCHIVE
            for m in memories:
                m.status = MemoryStatus.ARCHIVED

        await db.commit()

        # Invalidate workspace semantic cache
        try:
            from app.ai.semantic_cache import SemanticCache

            await SemanticCache.invalidate(workspace_id)
        except Exception as e:
            logger.warning("Cache invalidation post sleep cycle failed: %s", e)

        # Record audit log
        await SecurityAuditLogger.log_event(
            db=db,
            action="memory.sleep_cycle_executed",
            workspace_id=workspace_id,
            user_id=user_id,
            details={
                "action": request.action,
                "processed_count": len(memories),
                "compacted_memory_id": compacted_id,
            },
        )

        return SleepCycleExecutionResponse(
            workspace_id=workspace_id,
            action_executed=request.action,
            processed_count=len(memories),
            compacted_memory_id=compacted_id,
            executed_at=now_dt,
        )
