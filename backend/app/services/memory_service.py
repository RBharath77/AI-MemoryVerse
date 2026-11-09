import csv
import io
import logging
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import String, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

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
    MemoryAutoConsolidateRequest,
    MemoryConflictResolutionRequest,
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
        # 0. Enforce Workspace DLP Policy
        from app.core.dlp import WorkspaceDLPService
        from app.models.workspace import Workspace

        ws_res = await db.execute(select(Workspace.settings).where(Workspace.id == workspace_id))
        ws_settings = ws_res.scalar_one_or_none()
        if ws_settings and isinstance(ws_settings, dict):
            dlp_cfg = ws_settings.get("dlp_policy")
            if dlp_cfg and dlp_cfg.get("enabled"):
                dlp_res = WorkspaceDLPService.inspect(data.content, dlp_cfg)
                if dlp_res.blocked:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"DLP Policy Violation: Memory ingestion blocked due to detected {dlp_res.violations}",
                    )
                data.content = dlp_res.sanitized_text

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

        # Generate cryptographic integrity signature & initialize access tracking
        now_dt = datetime.now(UTC)
        meta["integrity_signature"] = MemoryService.compute_integrity_signature(
            workspace_id=workspace_id,
            memory_id=memory.id,
            content=memory.content,
            category=memory.category.value,
            importance=memory.importance,
        )
        meta["access_count"] = 1
        meta["last_accessed_at"] = now_dt.isoformat()
        memory.extra_metadata = dict(meta)
        flag_modified(memory, "extra_metadata")

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
        from app.ai.semantic_cache import SemanticCache

        SemanticCache.invalidate_workspace(workspace_id)
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

            from app.core.sanitizer import CredentialSanitizer

            clean_fact_content = CredentialSanitizer.redact(fact.content).sanitized_text

            try:
                emb = await embedder.get_embedding(clean_fact_content)
            except Exception:
                emb = None

            mem = Memory(
                workspace_id=workspace_id,
                user_id=user_id,
                content=clean_fact_content,
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

            now_dt = datetime.now(UTC)
            meta = dict(mem.extra_metadata or {})
            meta["integrity_signature"] = MemoryService.compute_integrity_signature(
                workspace_id=workspace_id,
                memory_id=mem.id,
                content=mem.content,
                category=mem.category.value
                if hasattr(mem.category, "value")
                else str(mem.category),
                importance=mem.importance,
            )
            meta["access_count"] = 1
            meta["last_accessed_at"] = now_dt.isoformat()
            mem.extra_metadata = meta

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
        from app.ai.semantic_cache import SemanticCache

        SemanticCache.invalidate_workspace(workspace_id)

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
        is_admin_or_owner: bool = False,
    ) -> Memory:
        memory = await MemoryService.get_memory(db, workspace_id, memory_id)
        if memory.user_id != user_id and not is_admin_or_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update this memory.",
            )

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

        # Re-compute cryptographic integrity signature upon modification
        meta = dict(memory.extra_metadata or {})
        meta["integrity_signature"] = MemoryService.compute_integrity_signature(
            workspace_id=workspace_id,
            memory_id=memory.id,
            content=memory.content,
            category=memory.category.value
            if hasattr(memory.category, "value")
            else str(memory.category),
            importance=memory.importance,
        )
        memory.extra_metadata = meta
        flag_modified(memory, "extra_metadata")

        await db.commit()
        await db.refresh(memory)
        from app.ai.semantic_cache import SemanticCache

        SemanticCache.invalidate_workspace(workspace_id)
        return memory

    @staticmethod
    async def delete_memory(
        db: AsyncSession,
        workspace_id: str,
        memory_id: str,
        current_user_id: str | None = None,
        is_admin_or_owner: bool = False,
    ) -> bool:
        memory = await MemoryService.get_memory(db, workspace_id, memory_id)
        if current_user_id and memory.user_id != current_user_id and not is_admin_or_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete this memory.",
            )
        await db.delete(memory)
        await db.commit()
        from app.ai.semantic_cache import SemanticCache

        SemanticCache.invalidate_workspace(workspace_id)
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
        is_admin_or_owner: bool = False,
    ) -> Memory:
        memory = await MemoryService.get_memory(db, workspace_id, memory_id)
        if memory.user_id != user_id and not is_admin_or_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to restore this memory.",
            )

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
        from app.ai.semantic_cache import SemanticCache

        SemanticCache.invalidate_workspace(workspace_id)
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
        is_admin_or_owner: bool = False,
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
        if not memory or memory.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated memory not found or unauthorized.",
            )

        if memory.user_id != user_id and not is_admin_or_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to review this memory.",
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
            if action.corrected_text:
                from app.core.sanitizer import CredentialSanitizer

                clean_text = CredentialSanitizer.redact(action.corrected_text).sanitized_text
                review.corrected_text = clean_text
                memory.content = clean_text
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
                    content=clean_text,
                    category=memory.category.value,
                    changed_by_user_id=user_id,
                    change_reason="User corrected during review",
                )
                db.add(v)
            else:
                review.corrected_text = None
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

        from app.core.sanitizer import CredentialSanitizer

        for item in items:
            clean_content = CredentialSanitizer.redact(item.content).sanitized_text
            dup = ConflictDetector.check_duplicate(clean_content, existing_rows)
            if dup.is_duplicate and dup.similarity_score >= 0.90:
                skipped += 1
                continue

            mem = Memory(
                workspace_id=workspace_id,
                user_id=user_id,
                content=clean_content,
                category=item.category,
                status=MemoryStatus.APPROVED,
                importance=item.importance,
                confidence=1.0,
                source_type=item.source_type or "import",
                tags=item.tags or [],
            )
            db.add(mem)
            await db.flush()

            now_dt = datetime.now(UTC)
            meta = dict(mem.extra_metadata or {})
            meta["integrity_signature"] = MemoryService.compute_integrity_signature(
                workspace_id=workspace_id,
                memory_id=mem.id,
                content=mem.content,
                category=mem.category.value
                if hasattr(mem.category, "value")
                else str(mem.category),
                importance=mem.importance,
            )
            meta["access_count"] = 1
            meta["last_accessed_at"] = now_dt.isoformat()
            mem.extra_metadata = meta

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
        if source_memory_id == data.target_memory_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Source and target memories cannot be the same.",
            )

        # Tenancy verification for both source and target memories
        src = await MemoryService.get_memory(db, workspace_id, source_memory_id)
        target = await MemoryService.get_memory(db, workspace_id, data.target_memory_id)

        # Idempotency check for identical relationship
        existing_q = select(MemoryLink).where(
            MemoryLink.workspace_id == workspace_id,
            MemoryLink.source_memory_id == src.id,
            MemoryLink.target_memory_id == target.id,
            MemoryLink.relationship_type == data.relationship_type,
        )
        existing = (await db.execute(existing_q)).scalar_one_or_none()
        if existing:
            return existing

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

    @staticmethod
    def _calculate_similarity(m1: Memory, m2: Memory) -> float:
        # 1. Exact or normalized string match
        c1 = m1.content.strip().lower()
        c2 = m2.content.strip().lower()
        if c1 == c2:
            return 1.0

        # 2. Token-based Jaccard similarity
        import re

        tokens1 = set(re.findall(r"\w+", c1))
        tokens2 = set(re.findall(r"\w+", c2))
        token_sim = 0.0
        if tokens1 and tokens2:
            intersection = len(tokens1 & tokens2)
            union = len(tokens1 | tokens2)
            token_sim = (intersection / union) if union > 0 else 0.0

        # 3. Vector cosine similarity if both embeddings present
        vec_sim = 0.0
        if m1.embedding and m2.embedding and len(m1.embedding) == len(m2.embedding):
            import math

            dot = sum(a * b for a, b in zip(m1.embedding, m2.embedding))
            norm_a = math.sqrt(sum(a * a for a in m1.embedding))
            norm_b = math.sqrt(sum(b * b for b in m2.embedding))
            if norm_a > 0 and norm_b > 0:
                cos_sim = dot / (norm_a * norm_b)
                vec_sim = max(0.0, min(1.0, float(cos_sim)))

        return max(token_sim, vec_sim)

    @staticmethod
    async def deduplicate_workspace_memories(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        similarity_threshold: float = 0.90,
        auto_merge: bool = True,
    ) -> dict[str, Any]:
        from app.ai.semantic_cache import SemanticCache

        # Query all active approved memories in workspace, ordered by created_at ascending
        query = (
            select(Memory)
            .where(
                Memory.workspace_id == workspace_id,
                Memory.status == MemoryStatus.APPROVED,
            )
            .order_by(Memory.created_at.asc())
        )
        res = await db.execute(query)
        memories = list(res.scalars().all())

        scanned_count = len(memories)
        duplicates_found = 0
        consolidated_count = 0
        details = []

        superseded_set = set()

        for i in range(len(memories)):
            m_primary = memories[i]
            if m_primary.id in superseded_set:
                continue

            for j in range(i + 1, len(memories)):
                m_duplicate = memories[j]
                if m_duplicate.id in superseded_set:
                    continue

                sim = MemoryService._calculate_similarity(m_primary, m_duplicate)
                if sim >= similarity_threshold:
                    duplicates_found += 1
                    superseded_set.add(m_duplicate.id)

                    details.append(
                        {
                            "primary_id": m_primary.id,
                            "duplicate_id": m_duplicate.id,
                            "similarity": round(float(sim), 4),
                            "action": "superseded" if auto_merge else "flagged",
                        }
                    )

                    if auto_merge:
                        m_duplicate.status = MemoryStatus.SUPERSEDED
                        m_duplicate.superseded_by = m_primary.id

                        # Merge tags into primary
                        primary_tags = list(m_primary.tags or [])
                        dup_tags = list(m_duplicate.tags or [])
                        merged_tags = list(dict.fromkeys(primary_tags + dup_tags))
                        m_primary.tags = merged_tags

                        # Create link
                        link = MemoryLink(
                            workspace_id=workspace_id,
                            source_memory_id=m_duplicate.id,
                            target_memory_id=m_primary.id,
                            relationship_type="superseded_by",
                            confidence=round(float(sim), 4),
                        )
                        db.add(link)
                        consolidated_count += 1

        if consolidated_count > 0:
            await db.commit()
            SemanticCache.invalidate_workspace(workspace_id)

        return {
            "scanned_count": scanned_count,
            "duplicates_found": duplicates_found,
            "consolidated_count": consolidated_count,
            "details": details,
        }

    @staticmethod
    def compute_integrity_signature(
        workspace_id: str,
        memory_id: str,
        content: str,
        category: str,
        importance: int,
    ) -> str:
        """
        Cryptographic HMAC-SHA256 data integrity checksum.
        Detects unauthorized external SQL tampering or direct row alteration.
        """
        import hashlib
        import hmac

        from app.core.config import settings

        base = f"{workspace_id}:{memory_id}:{content}:{category}:{importance}".encode()
        secret = settings.SECRET_KEY.encode("utf-8")
        return hmac.new(secret, base, hashlib.sha256).hexdigest()

    @staticmethod
    def compute_retention_strength(
        memory: Memory,
        now: datetime | None = None,
    ) -> tuple[float, float, int]:
        """
        Biological Ebbinghaus Forgetting Curve: R(t) = exp(-t / S)
        Returns:
            (retention_strength: float 0..1, stability_days: float, access_count: int)
        """
        import math

        meta = memory.extra_metadata or {}
        access_count = int(meta.get("access_count", 1))

        if memory.is_pinned:
            return 1.0, 365.0, access_count

        current_time = now or datetime.now(UTC)
        base_stability = 30.0
        stability_days = base_stability * (1.0 + 0.5 * math.log(1.0 + access_count))

        last_str = meta.get("last_accessed_at")
        if last_str:
            try:
                dt = datetime.fromisoformat(last_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
            except Exception:
                dt = memory.created_at
        else:
            dt = memory.created_at

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        delta_days = max(0.0, (current_time - dt).total_seconds() / 86400.0)
        retention = math.exp(-delta_days / stability_days)
        return max(0.0, min(1.0, round(retention, 4))), round(stability_days, 2), access_count

    @staticmethod
    async def reinforce_memory(
        db: AsyncSession,
        workspace_id: str,
        memory_id: str,
        user_id: str,
    ) -> dict:
        """
        Active Memory Reinforcement: boosts stability factor and resets elapsed decay window.
        """
        memory = await MemoryService.get_memory(db, workspace_id, memory_id)
        now = datetime.now(UTC)
        meta = dict(memory.extra_metadata or {})
        access_count = int(meta.get("access_count", 0)) + 2
        meta["access_count"] = access_count
        meta["last_accessed_at"] = now.isoformat()
        meta["last_reinforced_at"] = now.isoformat()
        meta["integrity_signature"] = MemoryService.compute_integrity_signature(
            workspace_id=workspace_id,
            memory_id=memory.id,
            content=memory.content,
            category=memory.category.value
            if hasattr(memory.category, "value")
            else str(memory.category),
            importance=memory.importance,
        )
        memory.extra_metadata = meta
        flag_modified(memory, "extra_metadata")
        await db.commit()
        await db.refresh(memory)

        strength, stability, acc = MemoryService.compute_retention_strength(memory, now=now)
        return {
            "id": memory.id,
            "workspace_id": memory.workspace_id,
            "retention_strength": strength,
            "stability_days": stability,
            "access_count": acc,
            "last_reinforced_at": now,
        }

    @staticmethod
    async def get_decay_analytics(
        db: AsyncSession,
        workspace_id: str,
        now: datetime | None = None,
    ) -> dict:
        """
        Analyzes memory decay distribution across workspace using Ebbinghaus curve.
        Categorizes memories into Strong (>=0.70), Fading (0.30..0.70), and Dormant (<0.30).
        """
        q = select(Memory).where(
            Memory.workspace_id == workspace_id,
            Memory.status == MemoryStatus.APPROVED,
        )
        res = await db.execute(q)
        memories = list(res.scalars().all())

        total = len(memories)
        if total == 0:
            return {
                "total_memories": 0,
                "strong_count": 0,
                "fading_count": 0,
                "dormant_count": 0,
                "average_retention": 1.0,
                "dormant_memory_ids": [],
            }

        strong_count = 0
        fading_count = 0
        dormant_count = 0
        dormant_ids = []
        total_retention = 0.0

        for m in memories:
            strength, _, _ = MemoryService.compute_retention_strength(m, now=now)
            total_retention += strength
            if strength >= 0.70:
                strong_count += 1
            elif strength >= 0.30:
                fading_count += 1
            else:
                dormant_count += 1
                dormant_ids.append(m.id)

        avg_retention = round(total_retention / total, 4)
        return {
            "total_memories": total,
            "strong_count": strong_count,
            "fading_count": fading_count,
            "dormant_count": dormant_count,
            "average_retention": avg_retention,
            "dormant_memory_ids": dormant_ids,
        }

    @staticmethod
    async def verify_workspace_integrity(
        db: AsyncSession,
        workspace_id: str,
    ) -> dict:
        """
        Cryptographically verifies row-level HMAC-SHA256 signatures for all workspace memories.
        Detects unauthorized external direct SQL row edits or tampering.
        """
        import hmac

        q = select(Memory).where(Memory.workspace_id == workspace_id)
        res = await db.execute(q)
        memories = list(res.scalars().all())

        valid_count = 0
        tampered_count = 0
        tampered_ids = []

        for m in memories:
            meta = m.extra_metadata or {}
            stored_sig = meta.get("integrity_signature")
            expected_sig = MemoryService.compute_integrity_signature(
                workspace_id=m.workspace_id,
                memory_id=m.id,
                content=m.content,
                category=m.category.value if hasattr(m.category, "value") else str(m.category),
                importance=m.importance,
            )
            if stored_sig and hmac.compare_digest(stored_sig, expected_sig):
                valid_count += 1
            else:
                tampered_count += 1
                tampered_ids.append(m.id)

        return {
            "total_checked": len(memories),
            "valid_count": valid_count,
            "tampered_count": tampered_count,
            "tampered_ids": tampered_ids,
            "is_compromised": tampered_count > 0,
            "verified_at": datetime.now(UTC),
        }

    @staticmethod
    async def preview_conflict_diff(
        db: AsyncSession,
        workspace_id: str,
        memory_id: str,
        user_id: str,
    ) -> dict:
        """Preview fine-grained semantic fact diff between candidate memory and its conflicting counterpart."""
        memory = await MemoryService.get_memory(db, workspace_id, memory_id)
        conflicting_id = (memory.extra_metadata or {}).get("conflicting_memory_id")
        prev_mem = None
        if conflicting_id:
            prev_mem = await db.get(Memory, conflicting_id)

        from app.ai.fact_differ import SemanticFactDiffer

        diff = SemanticFactDiffer.compute_diff(
            old_content=prev_mem.content if prev_mem else "",
            new_content=memory.content,
        )
        return {
            "old_content": diff.old_content,
            "new_content": diff.new_content,
            "similarity_score": diff.similarity_score,
            "added_tokens": diff.added_tokens,
            "removed_tokens": diff.removed_tokens,
            "contradicted_entities": diff.contradicted_entities,
            "temporal_shift_summary": diff.temporal_shift_summary,
        }

    @staticmethod
    async def resolve_conflict(
        db: AsyncSession,
        workspace_id: str,
        memory_id: str,
        user_id: str,
        data: MemoryConflictResolutionRequest,
        is_admin_or_owner: bool = False,
    ) -> dict:
        """Interactively resolve candidate memory contradictions using supersede, merge, keep_both, or discard."""
        memory = await MemoryService.get_memory(db, workspace_id, memory_id)
        if memory.user_id != user_id and not is_admin_or_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to resolve conflict for this memory.",
            )

        strategy = data.strategy.lower().strip()
        if strategy not in ("supersede", "merge", "keep_both", "discard"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unsupported conflict resolution strategy '{data.strategy}'. "
                    f"Choose supersede, merge, keep_both, or discard."
                ),
            )

        meta = dict(memory.extra_metadata or {})
        conflicting_id = meta.get("conflicting_memory_id")
        prev_mem = None
        if conflicting_id:
            prev_mem = await db.get(Memory, conflicting_id)

        from app.ai.fact_differ import SemanticFactDiffer

        diff = SemanticFactDiffer.compute_diff(
            old_content=prev_mem.content if prev_mem else "",
            new_content=memory.content,
        )

        now_dt = datetime.now(UTC)

        if strategy == "supersede":
            memory.status = MemoryStatus.APPROVED
            if prev_mem:
                prev_mem.status = MemoryStatus.SUPERSEDED
                prev_mem.superseded_by = memory.id
                link = MemoryLink(
                    workspace_id=workspace_id,
                    source_memory_id=memory.id,
                    target_memory_id=prev_mem.id,
                    relationship_type="supersedes",
                    confidence=1.0,
                )
                db.add(link)

        elif strategy == "merge":
            if not data.merged_content or not data.merged_content.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parameter 'merged_content' is required when resolution strategy is 'merge'.",
                )
            # Record historical version
            v_num = 1
            max_v_res = await db.execute(
                select(func.max(MemoryVersion.version_number)).where(
                    MemoryVersion.memory_id == memory.id
                )
            )
            max_v = max_v_res.scalar()
            if max_v:
                v_num = max_v + 1

            new_v = MemoryVersion(
                memory_id=memory.id,
                version_number=v_num,
                content=memory.content,
                category=(
                    memory.category.value
                    if hasattr(memory.category, "value")
                    else str(memory.category)
                ),
                changed_by_user_id=user_id,
                change_reason=f"Synthesized merge conflict resolution: {data.notes or 'Consolidated facts'}",
            )
            db.add(new_v)

            memory.content = data.merged_content.strip()
            memory.status = MemoryStatus.APPROVED
            if prev_mem:
                prev_mem.status = MemoryStatus.SUPERSEDED
                prev_mem.superseded_by = memory.id

        elif strategy == "keep_both":
            memory.status = MemoryStatus.APPROVED
            meta["contextual_distinction"] = True
            if prev_mem:
                prev_meta = dict(prev_mem.extra_metadata or {})
                prev_meta["contextual_distinction"] = True
                prev_mem.extra_metadata = prev_meta
                flag_modified(prev_mem, "extra_metadata")

        elif strategy == "discard":
            memory.status = MemoryStatus.REJECTED
            meta["discard_reason"] = data.notes or "Discarded in favor of existing memory record."

        meta["conflict_resolved"] = True
        meta["conflict_resolution_strategy"] = strategy
        meta["conflict_resolved_at"] = now_dt.isoformat()
        if data.notes:
            meta["conflict_resolution_notes"] = data.notes

        memory.extra_metadata = meta
        flag_modified(memory, "extra_metadata")

        # Invalidate semantic cache
        from app.ai.semantic_cache import SemanticCache

        SemanticCache.invalidate_workspace(workspace_id)

        await db.commit()
        await db.refresh(memory)

        return {
            "resolved_memory_id": memory.id,
            "previous_memory_id": prev_mem.id if prev_mem else None,
            "strategy": strategy,
            "status": memory.status.value,
            "fact_diff": {
                "old_content": diff.old_content,
                "new_content": diff.new_content,
                "similarity_score": diff.similarity_score,
                "added_tokens": diff.added_tokens,
                "removed_tokens": diff.removed_tokens,
                "contradicted_entities": diff.contradicted_entities,
                "temporal_shift_summary": diff.temporal_shift_summary,
            },
            "resolved_at": now_dt,
        }

    @classmethod
    async def auto_consolidate_workspace_memories(
        cls,
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        request: MemoryAutoConsolidateRequest,
    ) -> dict[str, Any]:
        """Abstracts and consolidates granular episodic memories into high-order semantic principles."""
        from app.ai.consolidation import MemoryConsolidationEngine
        from app.ai.semantic_cache import SemanticCache
        from app.core.audit import SecurityAuditLogger

        # Fetch active approved memories for this workspace
        q = (
            select(Memory)
            .where(
                Memory.workspace_id == workspace_id,
                Memory.status == MemoryStatus.APPROVED,
            )
            .order_by(desc(Memory.created_at))
        )
        res = await db.execute(q)
        memories = list(res.scalars().all())

        clusters = MemoryConsolidationEngine.cluster_memories(
            memories=memories,
            min_memories=request.min_memories,
            target_topic=request.topic,
        )

        cluster_results = []
        source_id_map: dict[str, Memory] = {m.id: m for m in memories}
        total_source_count = 0
        now_dt = datetime.now(UTC)

        for cl in clusters:
            syn_data = MemoryConsolidationEngine.synthesize_cluster(cl)
            total_source_count += len(syn_data.source_memory_ids)
            cluster_results.append(
                {
                    "topic": syn_data.topic,
                    "source_memory_ids": syn_data.source_memory_ids,
                    "synthesized_content": syn_data.synthesized_content,
                    "confidence": syn_data.confidence,
                    "compression_ratio": syn_data.compression_ratio,
                    "source_categories": syn_data.source_categories,
                }
            )

        if request.dry_run:
            return {
                "clusters": cluster_results,
                "total_source_memories": total_source_count,
                "consolidated_memories_created": 0,
                "new_memory_ids": [],
                "dry_run": True,
                "consolidated_at": now_dt,
            }

        # Commit mode: persist new synthesized memories and links
        new_memory_ids: list[str] = []
        embedding_provider = get_embedding_provider()

        for c_data in cluster_results:
            emb = None
            try:
                emb = await embedding_provider.embed_query(c_data["synthesized_content"])
            except Exception as e:
                logger.warning("Failed to generate embedding for consolidated memory: %s", e)

            new_mem = Memory(
                workspace_id=workspace_id,
                user_id=user_id,
                content=c_data["synthesized_content"],
                category=request.target_category,
                status=MemoryStatus.APPROVED,
                source_type="consolidation",
                importance=8,
                confidence=c_data["confidence"],
                tags=["consolidated", "synthesized", c_data["topic"].lower()],
                extra_metadata={
                    "synthesized_from_ids": c_data["source_memory_ids"],
                    "cluster_topic": c_data["topic"],
                    "compression_ratio": c_data["compression_ratio"],
                    "consolidation_timestamp": now_dt.isoformat(),
                },
                embedding=emb,
            )
            db.add(new_mem)
            await db.flush()
            new_memory_ids.append(new_mem.id)

            # Create bidirectional MemoryLink
            for src_id in c_data["source_memory_ids"]:
                link = MemoryLink(
                    workspace_id=workspace_id,
                    source_memory_id=new_mem.id,
                    target_memory_id=src_id,
                    relationship_type="CONSOLIDATES",
                    confidence=c_data["confidence"],
                )
                db.add(link)

                # Annotate source memory
                src_mem = source_id_map.get(src_id)
                if src_mem:
                    src_meta = dict(src_mem.extra_metadata or {})
                    src_meta["consolidated_into"] = new_mem.id
                    src_mem.extra_metadata = src_meta
                    flag_modified(src_mem, "extra_metadata")

        SemanticCache.invalidate_workspace(workspace_id)
        await SecurityAuditLogger.log_event(
            db=db,
            action="memories.consolidate",
            workspace_id=workspace_id,
            user_id=user_id,
            details={
                "clusters_count": len(cluster_results),
                "total_source_memories": total_source_count,
                "new_memory_ids": new_memory_ids,
            },
        )
        await db.commit()

        return {
            "clusters": cluster_results,
            "total_source_memories": total_source_count,
            "consolidated_memories_created": len(new_memory_ids),
            "new_memory_ids": new_memory_ids,
            "dry_run": False,
            "consolidated_at": now_dt,
        }

    @classmethod
    async def get_memory_associations(
        cls,
        db: AsyncSession,
        workspace_id: str,
        memory_id: str,
        max_hops: int = 2,
        min_activation: float = 0.15,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Traverse spreading activation associative graph for seed memory."""
        from app.ai.associative_memory import AssociativeMemoryExplorer

        return await AssociativeMemoryExplorer.explore_associations(
            db=db,
            workspace_id=workspace_id,
            seed_memory_id=memory_id,
            max_hops=max_hops,
            min_activation=min_activation,
            limit=limit,
        )
