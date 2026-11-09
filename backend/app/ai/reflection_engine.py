from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory, MemoryCategory, MemoryLink, MemoryStatus
from app.schemas.memory import (
    ExistingReflectionsResponse,
    MemoryReflectionRequest,
    MemoryReflectionResponse,
    MemoryResponse,
    ReflectionInsightItem,
)

logger = logging.getLogger("memoryverse.reflection_engine")


class MemoryReflectionEngine:
    """
    Autonomous cognitive reflection & pattern synthesis engine.
    Analyzes episodic and semantic workspace memories over time to synthesize higher-order
    operational heuristics, architectural decisions, habits, and user preferences.
    """

    # Keyword classifiers for reflection categorization
    TOPIC_CLASSIFIERS: dict[str, dict[str, Any]] = {
        "architecture": {
            "keywords": [
                "fastapi",
                "sqlalchemy",
                "pydantic",
                "async",
                "next.js",
                "database",
                "postgres",
                "celery",
                "redis",
                "schema",
                "orm",
                "endpoint",
            ],
            "type": "architecture",
            "title": "System Architecture & Engineering Standards",
            "suggested_action": "Prioritize async ORM pipelines, strict Pydantic schemas, and modular domain patterns in future code generations.",
        },
        "security": {
            "keywords": [
                "security",
                "auth",
                "jwt",
                "hmac",
                "token",
                "ssrf",
                "injection",
                "mfa",
                "rbac",
                "encryption",
                "sanitizer",
                "dlp",
                "audit",
            ],
            "type": "heuristic",
            "title": "Zero-Trust Security & Cryptographic Integrity",
            "suggested_action": "Always enforce strict cryptographic signatures, input boundaries, and multi-tenant authorization guards.",
        },
        "quality": {
            "keywords": [
                "test",
                "pytest",
                "lint",
                "ruff",
                "coverage",
                "benchmark",
                "regression",
                "verify",
                "assert",
                "validation",
            ],
            "type": "habit",
            "title": "Continuous Automated Quality Verification",
            "suggested_action": "Require automated unit and integration tests and enforce zero-warning linter passes before marking work complete.",
        },
        "performance": {
            "keywords": [
                "cache",
                "latency",
                "redis",
                "hnsw",
                "vector",
                "embedding",
                "chunk",
                "throughput",
                "concurrency",
                "rate_limit",
                "batch",
            ],
            "type": "decision",
            "title": "High-Throughput Optimization & Semantic Caching",
            "suggested_action": "Utilize vector indexing, semantic response caching, and bounded memory pools to maintain low query latency.",
        },
        "ui_experience": {
            "keywords": [
                "ui",
                "frontend",
                "dark",
                "tailwind",
                "contrast",
                "theme",
                "streaming",
                "component",
                "accessibility",
                "responsive",
            ],
            "type": "preference",
            "title": "Interface Aesthetics & User Experience Standards",
            "suggested_action": "Maintain high-contrast accessible layouts, responsive dark/light themes, and real-time SSE streaming indicators.",
        },
    }

    @classmethod
    async def reflect(
        cls,
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        request: MemoryReflectionRequest,
    ) -> MemoryReflectionResponse:
        """
        Reflect over active workspace memories to discover recurring themes,
        synthesize principles, and optionally persist them as reflective semantic memories.
        """
        now_dt = datetime.now(UTC)
        cutoff_dt = now_dt - timedelta(days=request.lookback_days)

        # 1. Fetch active workspace memories in lookback window
        stmt = (
            select(Memory)
            .where(
                Memory.workspace_id == workspace_id,
                Memory.status.in_([MemoryStatus.APPROVED, MemoryStatus.PENDING_REVIEW]),
                Memory.created_at >= cutoff_dt,
            )
            .order_by(desc(Memory.importance), desc(Memory.created_at))
            .limit(request.max_memories)
        )
        memories = list((await db.execute(stmt)).scalars().all())

        if not memories:
            # Fallback query without cutoff date if lookback window has few memories
            fallback_stmt = (
                select(Memory)
                .where(
                    Memory.workspace_id == workspace_id,
                    Memory.status.in_([MemoryStatus.APPROVED, MemoryStatus.PENDING_REVIEW]),
                )
                .order_by(desc(Memory.created_at))
                .limit(request.max_memories)
            )
            memories = list((await db.execute(fallback_stmt)).scalars().all())

        if not memories:
            return MemoryReflectionResponse(
                workspace_id=workspace_id,
                total_memories_analyzed=0,
                total_reflections_generated=0,
                insights=[],
                committed_memory_ids=[],
                auto_committed=request.auto_commit,
                reflected_at=now_dt,
            )

        # 2. Cluster memories by topic & extract reflections
        cluster_buckets: dict[str, list[Memory]] = defaultdict(list)
        unclassified_memories: list[Memory] = []

        for mem in memories:
            text_lower = f"{mem.content} {' '.join(mem.tags or [])}".lower()
            matched_topic = False

            for topic_key, topic_meta in cls.TOPIC_CLASSIFIERS.items():
                if any(kw in text_lower for kw in topic_meta["keywords"]):
                    cluster_buckets[topic_key].append(mem)
                    matched_topic = True

            if not matched_topic:
                unclassified_memories.append(mem)

        # 3. Formulate synthesized ReflectionInsightItems
        insights: list[ReflectionInsightItem] = []

        for topic_key, cluster_mems in cluster_buckets.items():
            if not cluster_mems:
                continue

            # If user provided focus_area and topic does not match, filter
            if (
                request.focus_area
                and request.focus_area.lower() not in topic_key
                and topic_key not in request.focus_area.lower()
            ):
                continue

            meta = cls.TOPIC_CLASSIFIERS[topic_key]
            source_ids = [m.id for m in cluster_mems]
            sample_snippets = [m.content.strip().replace("\n", " ") for m in cluster_mems[:3]]

            # Synthesize statement
            joined_snippets = "; ".join(sample_snippets)
            statement = (
                f"Consolidated reflection on {meta['title']}: "
                f"Observed {len(cluster_mems)} episodic patterns emphasizing: {joined_snippets}."
            )
            confidence = min(0.99, round(0.70 + (len(cluster_mems) * 0.05), 2))

            insight = ReflectionInsightItem(
                id=str(uuid.uuid4()),
                title=meta["title"],
                insight_type=meta["type"],
                statement=statement,
                confidence=confidence,
                source_memory_ids=source_ids,
                suggested_action=meta["suggested_action"],
                tags=[topic_key, "reflection", meta["type"]],
            )
            insights.append(insight)

        # General synthesis if no specific cluster matched or unclassified exists
        if not insights and unclassified_memories:
            general_ids = [m.id for m in unclassified_memories[:5]]
            gen_snippets = "; ".join(m.content.strip() for m in unclassified_memories[:3])
            insights.append(
                ReflectionInsightItem(
                    id=str(uuid.uuid4()),
                    title="Emergent Workspace Operational Pattern",
                    insight_type="heuristic",
                    statement=f"Synthesized general user directives and knowledge items: {gen_snippets}.",
                    confidence=0.85,
                    source_memory_ids=general_ids,
                    suggested_action="Incorporate these synthesized knowledge patterns across context assembly.",
                    tags=["general", "reflection", "heuristic"],
                )
            )

        committed_ids: list[str] = []

        # 4. Optional Auto-Commit to database as permanent semantic memories
        if request.auto_commit and insights:
            for item in insights:
                new_mem = Memory(
                    id=item.id,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    content=item.statement,
                    category=MemoryCategory.SEMANTIC,
                    status=MemoryStatus.APPROVED,
                    importance=9,
                    confidence=item.confidence,
                    is_pinned=True,
                    tags=list(set(item.tags + ["reflection", "synthesized_pattern"])),
                    source_type="reflection_engine",
                    extra_metadata={
                        "is_reflection": True,
                        "reflection_title": item.title,
                        "insight_type": item.insight_type,
                        "source_memory_ids": item.source_memory_ids,
                        "suggested_action": item.suggested_action,
                        "reflected_at": now_dt.isoformat(),
                    },
                )
                db.add(new_mem)
                committed_ids.append(new_mem.id)

                # Create MemoryLinks referencing each source memory
                for src_id in item.source_memory_ids:
                    link = MemoryLink(
                        id=str(uuid.uuid4()),
                        workspace_id=workspace_id,
                        source_memory_id=new_mem.id,
                        target_memory_id=src_id,
                        relationship_type="REFLECTS_ON",
                        confidence=item.confidence,
                    )
                    db.add(link)

            await db.commit()

            # Invalidate semantic cache for this workspace so reflection is hot
            try:
                from app.ai.semantic_cache import SemanticCache

                await SemanticCache.invalidate(workspace_id)
            except Exception as e:
                logger.warning("Cache invalidation error post reflection: %s", e)

        return MemoryReflectionResponse(
            workspace_id=workspace_id,
            total_memories_analyzed=len(memories),
            total_reflections_generated=len(insights),
            insights=insights,
            committed_memory_ids=committed_ids,
            auto_committed=request.auto_commit,
            reflected_at=now_dt,
        )

    @classmethod
    async def get_existing_reflections(
        cls,
        db: AsyncSession,
        workspace_id: str,
        limit: int = 50,
    ) -> ExistingReflectionsResponse:
        """Query previously committed reflections stored as semantic memories."""
        stmt = (
            select(Memory)
            .where(
                Memory.workspace_id == workspace_id,
                Memory.status != MemoryStatus.SUPERSEDED,
            )
            .order_by(desc(Memory.created_at))
            .limit(limit * 3)  # Scan broader pool then filter
        )
        memories = list((await db.execute(stmt)).scalars().all())

        reflection_memories: list[Memory] = []
        for m in memories:
            tags = m.tags or []
            meta = m.extra_metadata or {}
            if "reflection" in tags or meta.get("is_reflection") is True:
                reflection_memories.append(m)
            if len(reflection_memories) >= limit:
                break

        return ExistingReflectionsResponse(
            workspace_id=workspace_id,
            total_reflections=len(reflection_memories),
            reflections=[MemoryResponse.model_validate(m) for m in reflection_memories],
        )
