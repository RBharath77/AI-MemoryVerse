import csv
import io
import logging
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import String, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.conflict_detector import ConflictDetector
from app.ai.factory import get_embedding_provider
from app.ai.memory_extractor import MemoryExtractor
from app.models.memory import (
    Memory,
    MemoryCategory,
    MemoryFeedback,
    MemoryLink,
    MemoryReview,
    MemoryStatus,
    MemoryVersion,
)
from app.schemas.memory import (
    MemoryConsolidateRequest,
    MemoryCreate,
    MemoryExtractionRequest,
    MemoryExtractionResponse,
    MemoryFeedbackCreate,
    MemoryImportItem,
    MemoryLinkCreate,
    MemoryResponse,
    MemoryReviewAction,
    MemoryUpdate,
)

logger = logging.getLogger(__name__)


class MemoryService:
    @staticmethod
    async def create_memory(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        data: MemoryCreate,
    ) -> Memory:
        # 1. Fetch active workspace memories for duplicate and contradiction check
        existing_res = await db.execute(
            select(Memory.id, Memory.content, Memory.category).where(
                Memory.workspace_id == workspace_id,
                Memory.status == MemoryStatus.APPROVED,
            )
        )
        existing_rows = [
            {
                "id": r[0],
                "content": r[1],
                "category": r[2].value if hasattr(r[2], "value") else str(r[2]),
            }
            for r in existing_res.all()
        ]

        # 2. Check duplicates
        dup_result = ConflictDetector.check_duplicate(data.content, existing_rows)
        if dup_result.is_duplicate and dup_result.similarity_score >= 0.95:
            # Return existing or raise conflict
            existing_mem = await db.get(Memory, dup_result.duplicate_memory_id)
            if existing_mem:
                return existing_mem

        # 3. Check contradictions
        conflict_result = ConflictDetector.check_contradiction(data.content, existing_rows)

        initial_status = MemoryStatus.APPROVED
        meta = dict(data.extra_metadata or {})

        if conflict_result.is_conflict:
            initial_status = MemoryStatus.PENDING_REVIEW
            meta["conflict_detected"] = True
            meta["conflict_type"] = conflict_result.conflict_type
            meta["conflicting_memory_id"] = conflict_result.conflicting_memory_id
            meta["conflict_explanation"] = conflict_result.explanation

        embedder = get_embedding_provider()
        try:
            emb = await embedder.get_embedding(data.content)
        except Exception as e:
            logger.warning(f"Failed to generate embedding for memory: {e}")
            emb = None

        memory = Memory(
            workspace_id=workspace_id,
            user_id=user_id,
            content=data.content,
            category=data.category,
            status=initial_status,
            importance=data.importance,
            confidence=data.confidence,
            is_pinned=data.is_pinned,
            valid_from=data.valid_from or datetime.now(UTC),
            valid_until=data.valid_until,
            source_type=data.source_type,
            source_id=data.source_id,
            tags=data.tags or [],
            extra_metadata=meta,
            embedding=emb,
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

        # If pending review due to conflict or low confidence, create review item
        if initial_status == MemoryStatus.PENDING_REVIEW:
            review_item = MemoryReview(
                workspace_id=workspace_id,
                memory_id=memory.id,
                review_status="pending",
                original_text=memory.content,
                review_notes=conflict_result.explanation or "Flagged for user review.",
            )
            db.add(review_item)

        await db.commit()
        await db.refresh(memory)
        return memory

    @staticmethod
    async def extract_and_store_memories(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        data: MemoryExtractionRequest,
    ) -> MemoryExtractionResponse:
        extractor = MemoryExtractor()
        embedder = get_embedding_provider()
        facts = await extractor.extract_facts(data.text)

        # Fetch active memories for conflict checking
        existing_res = await db.execute(
            select(Memory.id, Memory.content, Memory.category).where(
                Memory.workspace_id == workspace_id,
                Memory.status == MemoryStatus.APPROVED,
            )
        )
        existing_rows = [
            {
                "id": r[0],
                "content": r[1],
                "category": r[2].value if hasattr(r[2], "value") else str(r[2]),
            }
            for r in existing_res.all()
        ]

        stored_memories: list[Memory] = []
        approved_count = 0
        pending_count = 0

        for fact in facts:
            # Check duplicate
            dup = ConflictDetector.check_duplicate(fact.content, existing_rows)
            if dup.is_duplicate and dup.similarity_score >= 0.90:
                continue  # Skip duplicate

            # Check conflict
            conflict = ConflictDetector.check_contradiction(fact.content, existing_rows)

            category_enum = MemoryCategory.SEMANTIC
            try:
                category_enum = MemoryCategory(fact.category.lower())
            except ValueError:
                category_enum = MemoryCategory.SEMANTIC

            # Determine approval status
            should_approve = (
                data.auto_approve and fact.confidence >= 0.8 and not conflict.is_conflict
            )
            mem_status = MemoryStatus.APPROVED if should_approve else MemoryStatus.PENDING_REVIEW

            meta: dict[str, Any] = {
                "extracted_from": data.source_type,
                "confidence_score": fact.confidence,
            }
            if conflict.is_conflict:
                meta["conflict_detected"] = True
                meta["conflicting_memory_id"] = conflict.conflicting_memory_id
                meta["conflict_explanation"] = conflict.explanation

            try:
                emb = await embedder.get_embedding(fact.content)
            except Exception:
                emb = None

            mem = Memory(
                workspace_id=workspace_id,
                user_id=user_id,
                content=fact.content,
                category=category_enum,
                status=mem_status,
                importance=fact.importance,
                confidence=fact.confidence,
                source_type=data.source_type,
                source_id=data.source_id,
                tags=fact.tags or [],
                extra_metadata=meta,
                embedding=emb,
            )
            db.add(mem)
            await db.flush()

            v = MemoryVersion(
                memory_id=mem.id,
                version_number=1,
                content=mem.content,
                category=mem.category.value,
                changed_by_user_id=user_id,
                change_reason="Extracted from conversation/document",
            )
            db.add(v)

            if mem_status == MemoryStatus.PENDING_REVIEW:
                rev = MemoryReview(
                    workspace_id=workspace_id,
                    memory_id=mem.id,
                    review_status="pending",
                    original_text=mem.content,
                    review_notes=conflict.explanation
                    if conflict.is_conflict
                    else "Extracted fact pending approval.",
                )
                db.add(rev)
                pending_count += 1
            else:
                approved_count += 1

            stored_memories.append(mem)
            # Add newly added memory to existing rows for intra-extraction deduplication
            existing_rows.append(
                {"id": mem.id, "content": mem.content, "category": mem.category.value}
            )

        await db.commit()
        for m in stored_memories:
            await db.refresh(m)

        return MemoryExtractionResponse(
            extracted_count=len(facts),
            approved_count=approved_count,
            pending_review_count=pending_count,
            memories=[MemoryResponse.model_validate(m) for m in stored_memories],
        )

    @staticmethod
    async def list_memories(
        db: AsyncSession,
        workspace_id: str,
        category: MemoryCategory | None = None,
        status: MemoryStatus | None = None,
        search: str | None = None,
        is_pinned: bool | None = None,
        active_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Memory], int]:
        query = select(Memory).where(Memory.workspace_id == workspace_id)

        if category:
            query = query.where(Memory.category == category)
        if status:
            query = query.where(Memory.status == status)
        if is_pinned is not None:
            query = query.where(Memory.is_pinned == is_pinned)
        if active_only:
            now = datetime.now(UTC)
            query = query.where(
                Memory.status == MemoryStatus.APPROVED,
                or_(Memory.valid_until.is_(None), Memory.valid_until > now),
            )
        if search:
            query = query.where(
                or_(
                    Memory.content.ilike(f"%{search}%"),
                    Memory.tags.cast(String).ilike(f"%{search}%"),
                )
            )

        # Count total
        count_query = select(func.count(Memory.id)).where(Memory.workspace_id == workspace_id)
        if category:
            count_query = count_query.where(Memory.category == category)
        if status:
            count_query = count_query.where(Memory.status == status)
        if is_pinned is not None:
            count_query = count_query.where(Memory.is_pinned == is_pinned)
        if active_only:
            now = datetime.now(UTC)
            count_query = count_query.where(
                Memory.status == MemoryStatus.APPROVED,
                or_(Memory.valid_until.is_(None), Memory.valid_until > now),
            )
        if search:
            count_query = count_query.where(
                or_(
                    Memory.content.ilike(f"%{search}%"),
                    Memory.tags.cast(String).ilike(f"%{search}%"),
                )
            )

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        # Sort pinned first, then newest
        query = (
            query.order_by(
                desc(Memory.is_pinned),
                desc(Memory.created_at),
            )
            .limit(limit)
            .offset(offset)
        )

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

        content_changed = data.content is not None and data.content != memory.content

        if content_changed:
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
        if data.confidence is not None:
            memory.confidence = data.confidence
        if data.is_pinned is not None:
            memory.is_pinned = data.is_pinned
        if data.tags is not None:
            memory.tags = data.tags
        if data.valid_from is not None:
            memory.valid_from = data.valid_from
        if data.valid_until is not None:
            memory.valid_until = data.valid_until
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

    @staticmethod
    async def get_versions(
        db: AsyncSession,
        workspace_id: str,
        memory_id: str,
    ) -> list[MemoryVersion]:
        # Validate tenancy
        await MemoryService.get_memory(db, workspace_id, memory_id)

        query = (
            select(MemoryVersion)
            .where(MemoryVersion.memory_id == memory_id)
            .order_by(desc(MemoryVersion.version_number))
        )
        res = await db.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def restore_version(
        db: AsyncSession,
        workspace_id: str,
        memory_id: str,
        user_id: str,
        version_number: int,
    ) -> Memory:
        memory = await MemoryService.get_memory(db, workspace_id, memory_id)

        v_query = select(MemoryVersion).where(
            MemoryVersion.memory_id == memory_id,
            MemoryVersion.version_number == version_number,
        )
        res = await db.execute(v_query)
        target_version = res.scalar_one_or_none()
        if not target_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version_number} does not exist for this memory.",
            )

        # Get highest version number
        latest_res = await db.execute(
            select(func.max(MemoryVersion.version_number)).where(
                MemoryVersion.memory_id == memory_id
            )
        )
        max_v = latest_res.scalar() or 1
        new_version_num = max_v + 1

        # Revert content
        memory.content = target_version.content
        try:
            memory.category = MemoryCategory(target_version.category)
        except ValueError:
            pass

        # Record restoration version
        new_v = MemoryVersion(
            memory_id=memory.id,
            version_number=new_version_num,
            content=memory.content,
            category=memory.category.value,
            changed_by_user_id=user_id,
            change_reason=f"Restored from version {version_number}",
        )
        db.add(new_v)
        await db.commit()
        await db.refresh(memory)
        return memory

    @staticmethod
    async def list_reviews(
        db: AsyncSession,
        workspace_id: str,
        status_filter: str | None = "pending",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MemoryReview], int]:
        query = select(MemoryReview).where(MemoryReview.workspace_id == workspace_id)
        if status_filter:
            query = query.where(MemoryReview.review_status == status_filter)

        count_query = select(func.count(MemoryReview.id)).where(
            MemoryReview.workspace_id == workspace_id
        )
        if status_filter:
            count_query = count_query.where(MemoryReview.review_status == status_filter)

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        query = query.order_by(desc(MemoryReview.created_at)).limit(limit).offset(offset)
        res = await db.execute(query)
        return list(res.scalars().all()), total

    @staticmethod
    async def act_on_review(
        db: AsyncSession,
        workspace_id: str,
        review_id: str,
        user_id: str,
        action: MemoryReviewAction,
    ) -> MemoryReview:
        query = select(MemoryReview).where(
            MemoryReview.id == review_id,
            MemoryReview.workspace_id == workspace_id,
        )
        res = await db.execute(query)
        review = res.scalar_one_or_none()
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory review item not found or unauthorized.",
            )

        memory = await db.get(Memory, review.memory_id)
        if not memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated memory not found.",
            )

        act = action.review_status.lower()
        now = datetime.now(UTC)

        review.reviewer_user_id = user_id
        review.reviewed_at = now
        review.review_notes = action.review_notes

        if act == "approved":
            review.review_status = "approved"
            memory.status = MemoryStatus.APPROVED
        elif act == "rejected":
            review.review_status = "rejected"
            memory.status = MemoryStatus.REJECTED
        elif act == "corrected":
            review.review_status = "corrected"
            review.corrected_text = action.corrected_text
            if action.corrected_text:
                memory.content = action.corrected_text
                # Log version
                latest_res = await db.execute(
                    select(func.max(MemoryVersion.version_number)).where(
                        MemoryVersion.memory_id == memory.id
                    )
                )
                max_v = latest_res.scalar() or 1
                v = MemoryVersion(
                    memory_id=memory.id,
                    version_number=max_v + 1,
                    content=action.corrected_text,
                    category=memory.category.value,
                    changed_by_user_id=user_id,
                    change_reason="User corrected during review",
                )
                db.add(v)
            memory.status = MemoryStatus.APPROVED
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid review action. Must be 'approved', 'rejected', or 'corrected'.",
            )

        await db.commit()
        await db.refresh(review)
        return review

    @staticmethod
    async def consolidate_memories(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        data: MemoryConsolidateRequest,
    ) -> Memory:
        # Validate that all memory IDs belong to this workspace
        q = select(Memory).where(
            Memory.id.in_(data.memory_ids),
            Memory.workspace_id == workspace_id,
        )
        res = await db.execute(q)
        source_memories = list(res.scalars().all())

        if len(source_memories) < len(data.memory_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more specified memories do not exist in this workspace.",
            )

        # Create consolidated memory
        consolidated = Memory(
            workspace_id=workspace_id,
            user_id=user_id,
            content=data.consolidated_content,
            category=data.category,
            status=MemoryStatus.APPROVED,
            importance=data.importance,
            confidence=1.0,
            source_type="consolidation",
            tags=list(set(data.tags + ["consolidated"])),
            extra_metadata={"consolidated_from": [m.id for m in source_memories]},
        )
        db.add(consolidated)
        await db.flush()

        v = MemoryVersion(
            memory_id=consolidated.id,
            version_number=1,
            content=consolidated.content,
            category=consolidated.category.value,
            changed_by_user_id=user_id,
            change_reason="Consolidated from multiple memories",
        )
        db.add(v)

        # Mark source memories as superseded
        for sm in source_memories:
            sm.status = MemoryStatus.SUPERSEDED
            sm.superseded_by = consolidated.id

            # Add relationship link
            link = MemoryLink(
                workspace_id=workspace_id,
                source_memory_id=sm.id,
                target_memory_id=consolidated.id,
                relationship_type="consolidated_into",
                confidence=1.0,
            )
            db.add(link)

        await db.commit()
        await db.refresh(consolidated)
        return consolidated

    @staticmethod
    async def get_timeline(
        db: AsyncSession,
        workspace_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = (
            select(Memory)
            .where(Memory.workspace_id == workspace_id)
            .order_by(desc(Memory.valid_from))
            .limit(limit)
        )
        res = await db.execute(query)
        memories = res.scalars().all()

        return [
            {
                "id": m.id,
                "content": m.content,
                "category": m.category.value,
                "importance": m.importance,
                "timestamp": m.valid_from or m.created_at,
                "source_type": m.source_type,
                "status": m.status.value,
            }
            for m in memories
        ]

    @staticmethod
    async def export_memories(
        db: AsyncSession,
        workspace_id: str,
        export_format: str = "json",
    ) -> tuple[str, str]:
        """Export workspace memories as JSON string or CSV string with MIME type."""
        query = (
            select(Memory)
            .where(
                Memory.workspace_id == workspace_id,
                Memory.status != MemoryStatus.REJECTED,
            )
            .order_by(desc(Memory.created_at))
        )

        res = await db.execute(query)
        memories = list(res.scalars().all())

        if export_format.lower() == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "id",
                    "content",
                    "category",
                    "status",
                    "importance",
                    "confidence",
                    "source_type",
                    "created_at",
                ]
            )
            for m in memories:
                writer.writerow(
                    [
                        m.id,
                        m.content,
                        m.category.value,
                        m.status.value,
                        m.importance,
                        m.confidence,
                        m.source_type,
                        m.created_at.isoformat() if m.created_at else "",
                    ]
                )
            return output.getvalue(), "text/csv"

        import json

        data = [
            {
                "id": m.id,
                "content": m.content,
                "category": m.category.value,
                "status": m.status.value,
                "importance": m.importance,
                "confidence": m.confidence,
                "source_type": m.source_type,
                "tags": m.tags,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in memories
        ]
        return json.dumps(data, indent=2), "application/json"

    @staticmethod
    async def import_memories(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        items: list[MemoryImportItem],
    ) -> tuple[int, int]:
        existing_res = await db.execute(
            select(Memory.id, Memory.content).where(Memory.workspace_id == workspace_id)
        )
        existing_rows = [{"id": r[0], "content": r[1]} for r in existing_res.all()]

        imported = 0
        skipped = 0

        for item in items:
            dup = ConflictDetector.check_duplicate(item.content, existing_rows)
            if dup.is_duplicate and dup.similarity_score >= 0.90:
                skipped += 1
                continue

            mem = Memory(
                workspace_id=workspace_id,
                user_id=user_id,
                content=item.content,
                category=item.category,
                status=MemoryStatus.APPROVED,
                importance=item.importance,
                confidence=1.0,
                source_type=item.source_type or "import",
                tags=item.tags or [],
            )
            db.add(mem)
            await db.flush()

            v = MemoryVersion(
                memory_id=mem.id,
                version_number=1,
                content=mem.content,
                category=mem.category.value,
                changed_by_user_id=user_id,
                change_reason="Bulk imported",
            )
            db.add(v)
            existing_rows.append({"id": mem.id, "content": mem.content})
            imported += 1

        await db.commit()
        return imported, skipped

    @staticmethod
    async def create_link(
        db: AsyncSession,
        workspace_id: str,
        source_memory_id: str,
        data: MemoryLinkCreate,
    ) -> MemoryLink:
        # Tenancy verification for both source and target memories
        src = await MemoryService.get_memory(db, workspace_id, source_memory_id)
        target = await MemoryService.get_memory(db, workspace_id, data.target_memory_id)

        link = MemoryLink(
            workspace_id=workspace_id,
            source_memory_id=src.id,
            target_memory_id=target.id,
            relationship_type=data.relationship_type,
            confidence=data.confidence,
        )
        db.add(link)
        await db.commit()
        await db.refresh(link)
        return link

    @staticmethod
    async def list_links(
        db: AsyncSession,
        workspace_id: str,
        memory_id: str,
    ) -> list[MemoryLink]:
        # Validate tenancy
        await MemoryService.get_memory(db, workspace_id, memory_id)

        query = select(MemoryLink).where(
            MemoryLink.workspace_id == workspace_id,
            or_(
                MemoryLink.source_memory_id == memory_id,
                MemoryLink.target_memory_id == memory_id,
            ),
        )
        res = await db.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def add_feedback(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        memory_id: str,
        data: MemoryFeedbackCreate,
    ) -> MemoryFeedback:
        await MemoryService.get_memory(db, workspace_id, memory_id)

        feedback = MemoryFeedback(
            workspace_id=workspace_id,
            memory_id=memory_id,
            user_id=user_id,
            rating=data.rating,
            feedback_text=data.feedback_text,
        )
        db.add(feedback)
        await db.commit()
        await db.refresh(feedback)
        return feedback

    @staticmethod
    async def get_analytics(
        db: AsyncSession,
        workspace_id: str,
    ) -> dict[str, Any]:
        query = select(Memory).where(Memory.workspace_id == workspace_id)
        res = await db.execute(query)
        memories = list(res.scalars().all())

        total = len(memories)
        approved = sum(1 for m in memories if m.status == MemoryStatus.APPROVED)
        pending = sum(1 for m in memories if m.status == MemoryStatus.PENDING_REVIEW)
        superseded = sum(1 for m in memories if m.status == MemoryStatus.SUPERSEDED)
        archived = sum(1 for m in memories if m.status == MemoryStatus.ARCHIVED)
        pinned = sum(1 for m in memories if m.is_pinned)

        by_cat = Counter(m.category.value for m in memories)
        all_tags = [t for m in memories for t in (m.tags or [])]
        tag_counts = Counter(all_tags)
        top_tags = [{"tag": t, "count": c} for t, c in tag_counts.most_common(10)]

        return {
            "total_memories": total,
            "approved_count": approved,
            "pending_review_count": pending,
            "superseded_count": superseded,
            "archived_count": archived,
            "pinned_count": pinned,
            "by_category": dict(by_cat),
            "top_tags": top_tags,
        }
