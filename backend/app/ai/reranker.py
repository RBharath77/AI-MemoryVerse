import math
from datetime import UTC, datetime

from app.ai.retrieval import SearchResultItem


class AdaptiveReranker:
    """
    Enterprise Adaptive RAG Reranker.
    Computes multi-factor contextual relevance combining:
    - Base semantic similarity & reciprocal rank fusion (RRF)
    - Temporal exponential recency decay (with pinned-memory protection)
    - Fact importance rating (1 to 10 scale)
    - User feedback signals (thumbs up/down)
    - Redundant candidate deduplication
    """

    MEMORY_HALF_LIFE_DAYS: float = 30.0
    DOCUMENT_HALF_LIFE_DAYS: float = 90.0

    @classmethod
    def calculate_recency_score(
        cls,
        created_at_str: str | None,
        is_pinned: bool = False,
        is_document: bool = False,
        now: datetime | None = None,
    ) -> float:
        if is_pinned:
            return 1.0  # Pinned principle facts never suffer recency decay

        if not created_at_str:
            return 0.5

        try:
            ca = datetime.fromisoformat(created_at_str)
            if ca.tzinfo is None:
                ca = ca.replace(tzinfo=UTC)
        except Exception:
            return 0.5

        current_time = now or datetime.now(UTC)
        delta_days = max(0.0, (current_time - ca).total_seconds() / 86400.0)
        half_life = cls.DOCUMENT_HALF_LIFE_DAYS if is_document else cls.MEMORY_HALF_LIFE_DAYS
        decay_constant = math.log(2) / half_life

        return math.exp(-decay_constant * delta_days)

    @classmethod
    def rerank(
        cls,
        candidates: list[SearchResultItem],
        top_k: int = 5,
        now: datetime | None = None,
    ) -> list[SearchResultItem]:
        if not candidates:
            return []

        scored = []
        for item in candidates:
            meta = item.metadata or {}
            is_pinned = bool(meta.get("is_pinned", False))
            is_doc = item.source_type == "document"
            created_at_str = meta.get("created_at")

            # 1. Base semantic/RRF score (normalized to 0..1 scale)
            base_score = min(1.0, max(0.0, float(item.score)))

            # 2. Recency decay factor
            recency_score = cls.calculate_recency_score(
                created_at_str=created_at_str,
                is_pinned=is_pinned,
                is_document=is_doc,
                now=now,
            )

            # 3. Importance score
            importance = meta.get("importance", 5)
            importance_score = min(1.0, max(0.1, importance / 10.0))

            # 4. Keyword exact-match bonus
            kw_score = meta.get("kw_score", 0.0)
            kw_bonus = 0.05 if kw_score > 0.5 else 0.0

            # 5. User feedback signal (-1, 0, +1)
            feedback_rating = meta.get("feedback_rating", 0)
            feedback_boost = (
                0.10 if feedback_rating > 0 else (-0.15 if feedback_rating < 0 else 0.0)
            )

            # 6. Composite scoring
            final_score = (
                (0.45 * base_score)
                + (0.25 * recency_score)
                + (0.15 * importance_score)
                + (0.10 * kw_bonus)
                + feedback_boost
            )
            final_score = max(0.0, min(1.0, round(final_score, 5)))

            meta["rerank_breakdown"] = {
                "base_score": round(base_score, 4),
                "recency_score": round(recency_score, 4),
                "importance_score": round(importance_score, 4),
                "kw_bonus": kw_bonus,
                "feedback_boost": feedback_boost,
            }

            scored.append((item, final_score))

        # Sort descending by composite final score
        scored.sort(key=lambda x: x[1], reverse=True)

        # Content deduplication
        seen_texts: set[str] = set()
        deduped: list[SearchResultItem] = []

        for item, final_score in scored:
            norm_content = " ".join(item.content.lower().split()[:20])
            if norm_content in seen_texts:
                continue
            seen_texts.add(norm_content)
            item.score = final_score
            deduped.append(item)
            if len(deduped) >= top_k:
                break

        return deduped


# Maintain backwards compatibility
Reranker = AdaptiveReranker
