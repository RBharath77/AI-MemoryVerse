from __future__ import annotations

import logging
import math
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.memory import Memory, MemoryStatus
from app.schemas.memory import (
    MemoryReviewCard,
    SpacedRepetitionReviewResponse,
    SpacedRepetitionReviewSubmit,
    SpacedRepetitionScheduleResponse,
)

logger = logging.getLogger("memoryverse.spaced_repetition")


class SpacedRepetitionScheduler:
    """
    Autonomous Temporal Memory Time-Decay Rejuvenation & Spaced Repetition Scheduler.
    Implements the SuperMemo SM-2 spaced repetition algorithm for workspace memories:
    tracks ease factor (EF), repetition intervals, retention probability, and optimal review dates.
    """

    @classmethod
    def calculate_sm2(
        cls,
        prev_repetition: int,
        prev_ease_factor: float,
        prev_interval_days: int,
        quality: int,
    ) -> tuple[int, float, int]:
        """Compute updated SM-2 repetition count, ease factor, and interval in days."""
        if quality < 3:
            # Recall failed; reset repetition count to 0 and interval to 1 day
            new_rep = 0
            new_interval = 1
            new_ef = prev_ease_factor
        else:
            # Successful recall
            if prev_repetition == 0:
                new_interval = 1
            elif prev_repetition == 1:
                new_interval = 6
            else:
                new_interval = max(1, round(prev_interval_days * prev_ease_factor))

            new_rep = prev_repetition + 1
            # EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
            delta_ef = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
            new_ef = max(1.3, min(2.5, round(prev_ease_factor + delta_ef, 2)))

        return new_rep, new_ef, new_interval

    @staticmethod
    def _ensure_utc(dt: datetime | None) -> datetime:
        if dt is None:
            return datetime.now(UTC)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    @classmethod
    async def get_schedule(
        cls,
        db: AsyncSession,
        workspace_id: str,
    ) -> SpacedRepetitionScheduleResponse:
        """Retrieve upcoming and overdue memories scheduled for spaced repetition review."""
        now_dt = datetime.now(UTC)

        stmt = select(Memory).where(
            Memory.workspace_id == workspace_id,
            Memory.status.in_([MemoryStatus.APPROVED, MemoryStatus.PENDING_REVIEW]),
        ).order_by(Memory.importance.desc())
        memories = list((await db.execute(stmt)).scalars().all())

        cards: list[MemoryReviewCard] = []
        due_now = 0
        upcoming = 0
        total_retention = 0.0

        for m in memories:
            sr_meta = (m.extra_metadata or {}).get("spaced_repetition", {})
            rep_num = sr_meta.get("repetition", 0)
            ef = sr_meta.get("ease_factor", 2.5)
            interval = sr_meta.get("interval_days", 1)

            last_rev_raw = sr_meta.get("last_reviewed_at")
            last_rev_dt = cls._ensure_utc(
                datetime.fromisoformat(last_rev_raw) if last_rev_raw else m.created_at
            )

            next_due_raw = sr_meta.get("next_review_due")
            if next_due_raw:
                next_due_dt = cls._ensure_utc(datetime.fromisoformat(next_due_raw))
            else:
                next_due_dt = last_rev_dt + timedelta(days=interval)

            is_overdue = now_dt >= next_due_dt
            if is_overdue:
                due_now += 1
            else:
                upcoming += 1

            # Retention probability R(t) = e^(-t / (S * EF))
            days_elapsed = max(0.0, (now_dt - last_rev_dt).total_seconds() / 86400.0)
            stability = max(1.0, (m.importance or 5) * (rep_num + 1) * 0.75)
            retention_prob = round(max(0.05, min(0.99, math.exp(-days_elapsed / (stability * ef)))), 2)
            total_retention += retention_prob

            cards.append(
                MemoryReviewCard(
                    memory_id=m.id,
                    content_snippet=m.content[:80] + "..." if len(m.content) > 80 else m.content,
                    category=m.category.value if hasattr(m.category, "value") else str(m.category),
                    repetition_number=rep_num,
                    ease_factor=ef,
                    interval_days=interval,
                    retention_probability=retention_prob,
                    last_reviewed_at=last_rev_dt,
                    next_review_due=next_due_dt,
                    is_overdue=is_overdue,
                )
            )

        avg_retention = round(total_retention / float(max(1, len(cards))), 2)

        return SpacedRepetitionScheduleResponse(
            workspace_id=workspace_id,
            total_cards=len(cards),
            due_now_count=due_now,
            upcoming_count=upcoming,
            average_retention_probability=avg_retention,
            cards=cards,
            generated_at=now_dt,
        )

    @classmethod
    async def submit_review(
        cls,
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        submit_data: SpacedRepetitionReviewSubmit,
    ) -> SpacedRepetitionReviewResponse:
        """Submit SM-2 review rating for memory and compute next review date."""
        now_dt = datetime.now(UTC)

        stmt = select(Memory).where(
            Memory.workspace_id == workspace_id,
            Memory.id == submit_data.memory_id,
        )
        memory = (await db.execute(stmt)).scalar_one_or_none()
        if not memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Memory '{submit_data.memory_id}' not found in workspace",
            )

        meta = dict(memory.extra_metadata or {})
        sr_meta = dict(meta.get("spaced_repetition", {}))

        prev_rep = sr_meta.get("repetition", 0)
        prev_ef = sr_meta.get("ease_factor", 2.5)
        prev_interval = sr_meta.get("interval_days", 1)

        new_rep, new_ef, new_interval = cls.calculate_sm2(
            prev_repetition=prev_rep,
            prev_ease_factor=prev_ef,
            prev_interval_days=prev_interval,
            quality=submit_data.rating,
        )

        next_due_dt = now_dt + timedelta(days=new_interval)

        sr_meta["repetition"] = new_rep
        sr_meta["ease_factor"] = new_ef
        sr_meta["interval_days"] = new_interval
        sr_meta["last_reviewed_at"] = now_dt.isoformat()
        sr_meta["next_review_due"] = next_due_dt.isoformat()
        sr_meta["last_rating"] = submit_data.rating
        sr_meta["reviewed_by"] = user_id

        meta["spaced_repetition"] = sr_meta
        memory.extra_metadata = meta
        flag_modified(memory, "extra_metadata")

        await db.commit()
        await db.refresh(memory)

        return SpacedRepetitionReviewResponse(
            workspace_id=workspace_id,
            memory_id=memory.id,
            previous_repetition=prev_rep,
            new_repetition=new_rep,
            previous_ease_factor=prev_ef,
            new_ease_factor=new_ef,
            new_interval_days=new_interval,
            next_review_due=next_due_dt,
            reviewed_at=now_dt,
        )
