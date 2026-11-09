from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.ai.retrieval import cosine_similarity
from app.models.memory import Memory

logger = logging.getLogger("memoryverse.drift_detector")


@dataclass
class TopicVelocityData:
    tag: str
    baseline_freq: int
    recent_freq: int
    acceleration: float


@dataclass
class MemoryDriftResult:
    workspace_id: str
    window_days: int
    baseline_memory_count: int
    recent_memory_count: int
    centroid_distance: float
    drift_score: float
    drift_status: str
    top_accelerating_topics: list[TopicVelocityData] = field(default_factory=list)
    top_declining_topics: list[TopicVelocityData] = field(default_factory=list)
    conflict_velocity_ratio: float = 0.0
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class MemoryDriftDetector:
    """Detects temporal concept drift, topic acceleration, and semantic centroid shifts across workspace memories."""

    STOPWORDS = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "by",
        "of",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "user",
        "prefers",
        "likes",
        "uses",
        "works",
    }

    @classmethod
    def _extract_tokens(cls, text: str) -> set[str]:
        tokens = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", text.lower())
        return {t for t in tokens if t not in cls.STOPWORDS}

    @classmethod
    def _compute_centroid(cls, vectors: list[list[float]]) -> list[float]:
        dim = len(vectors[0])
        centroid = [0.0] * dim
        for vec in vectors:
            for d in range(dim):
                centroid[d] += vec[d]
        n = len(vectors)
        return [v / n for v in centroid]

    @classmethod
    def _normalize_dt(cls, dt: datetime | None) -> datetime:
        if dt is None:
            return datetime.now(UTC)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt

    @classmethod
    def analyze_workspace_drift(
        cls,
        workspace_id: str,
        memories: list[Memory],
        window_days: int = 30,
    ) -> MemoryDriftResult:
        """Evaluate semantic centroid displacement and topic acceleration across temporal cohorts."""
        now_dt = datetime.now(UTC)

        if len(memories) < 2:
            return MemoryDriftResult(
                workspace_id=workspace_id,
                window_days=window_days,
                baseline_memory_count=len(memories),
                recent_memory_count=0,
                centroid_distance=0.0,
                drift_score=0.0,
                drift_status="STABLE",
                top_accelerating_topics=[],
                top_declining_topics=[],
                conflict_velocity_ratio=0.0,
                analyzed_at=now_dt,
            )

        cutoff = now_dt - timedelta(days=window_days)
        recent = [m for m in memories if cls._normalize_dt(m.created_at) >= cutoff]
        baseline = [m for m in memories if cls._normalize_dt(m.created_at) < cutoff]

        # If one cohort is empty, split memories chronologically in half
        if not recent or not baseline:
            sorted_mems = sorted(memories, key=lambda m: cls._normalize_dt(m.created_at))
            mid = len(sorted_mems) // 2
            baseline = sorted_mems[:mid]
            recent = sorted_mems[mid:]

        # 1. Semantic Centroid Drift
        base_vectors = [m.embedding for m in baseline if m.embedding is not None]
        rec_vectors = [m.embedding for m in recent if m.embedding is not None]

        if base_vectors and rec_vectors and len(base_vectors[0]) == len(rec_vectors[0]):
            c_base = cls._compute_centroid(base_vectors)
            c_rec = cls._compute_centroid(rec_vectors)
            sim = cosine_similarity(c_base, c_rec)
            centroid_distance = round(max(0.0, 1.0 - sim), 3)
        else:
            # Jaccard token overlap fallback
            base_tokens: set[str] = set()
            for m in baseline:
                base_tokens.update(cls._extract_tokens(m.content))
            rec_tokens: set[str] = set()
            for m in recent:
                rec_tokens.update(cls._extract_tokens(m.content))

            union = base_tokens | rec_tokens
            inter = base_tokens & rec_tokens
            jaccard = len(inter) / max(len(union), 1)
            centroid_distance = round(max(0.0, 1.0 - jaccard), 3)

        # 2. Topic / Tag Acceleration
        base_tags: list[str] = []
        for m in baseline:
            if m.tags and isinstance(m.tags, list):
                base_tags.extend([str(t).lower() for t in m.tags if t])
            base_tags.extend(list(cls._extract_tokens(m.content))[:2])

        rec_tags: list[str] = []
        for m in recent:
            if m.tags and isinstance(m.tags, list):
                rec_tags.extend([str(t).lower() for t in m.tags if t])
            rec_tags.extend(list(cls._extract_tokens(m.content))[:2])

        base_counter = Counter(base_tags)
        rec_counter = Counter(rec_tags)
        all_topics = set(base_counter.keys()) | set(rec_counter.keys())

        velocities: list[TopicVelocityData] = []
        n_base = max(len(baseline), 1)
        n_rec = max(len(recent), 1)

        for topic in all_topics:
            bf = base_counter.get(topic, 0)
            rf = rec_counter.get(topic, 0)
            accel = round((rf / n_rec) - (bf / n_base), 3)
            velocities.append(
                TopicVelocityData(
                    tag=topic,
                    baseline_freq=bf,
                    recent_freq=rf,
                    acceleration=accel,
                )
            )

        accelerating = sorted(
            [v for v in velocities if v.acceleration > 0],
            key=lambda x: x.acceleration,
            reverse=True,
        )[:5]
        declining = sorted(
            [v for v in velocities if v.acceleration < 0], key=lambda x: x.acceleration
        )[:5]

        # 3. Conflict / Volatility Drift
        recent_conflicts = sum(
            1
            for m in recent
            if getattr(m, "superseded_by", None) is not None
            or (m.extra_metadata and m.extra_metadata.get("conflict_resolved"))
        )
        conflict_ratio = round(recent_conflicts / max(len(recent), 1), 3)

        # 4. Composite Drift Score
        tag_drift = (
            round(
                sum(abs(v.acceleration) for v in velocities[:10]) / max(len(velocities[:10]), 1), 3
            )
            if velocities
            else 0.0
        )
        drift_score = round(
            min(1.0, 0.50 * centroid_distance + 0.30 * tag_drift + 0.20 * conflict_ratio), 3
        )

        if drift_score >= 0.55:
            drift_status = "HIGH_DRIFT"
        elif drift_score >= 0.25:
            drift_status = "MODERATE_DRIFT"
        else:
            drift_status = "STABLE"

        return MemoryDriftResult(
            workspace_id=workspace_id,
            window_days=window_days,
            baseline_memory_count=len(baseline),
            recent_memory_count=len(recent),
            centroid_distance=centroid_distance,
            drift_score=drift_score,
            drift_status=drift_status,
            top_accelerating_topics=accelerating,
            top_declining_topics=declining,
            conflict_velocity_ratio=conflict_ratio,
            analyzed_at=now_dt,
        )
