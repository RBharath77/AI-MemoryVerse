from app.ai.retrieval import SearchResultItem


class Reranker:
    """Reranks retrieved candidates using multi-factor signals (importance, pin state)."""

    @staticmethod
    def rerank(
        candidates: list[SearchResultItem],
        top_k: int = 5,
    ) -> list[SearchResultItem]:
        if not candidates:
            return []

        scored = []
        for item in candidates:
            adjusted_score = item.score

            # Priority boost for pinned memories
            if item.source_type == "memory" and item.metadata.get("is_pinned"):
                adjusted_score += 0.05

            # Importance weighting (1 - 10)
            importance = item.metadata.get("importance", 5)
            adjusted_score += (importance / 10.0) * 0.01

            # Exact keyword bonus
            if item.metadata.get("kw_score", 0.0) > 0.5:
                adjusted_score += 0.02

            scored.append((item, adjusted_score))

        # Sort descending by adjusted score
        scored.sort(key=lambda x: x[1], reverse=True)

        # Deduplicate redundant content
        seen_texts: set[str] = set()
        deduped: list[SearchResultItem] = []

        for item, final_score in scored:
            norm_content = " ".join(item.content.lower().split()[:20])
            if norm_content in seen_texts:
                continue
            seen_texts.add(norm_content)
            item.score = round(final_score, 5)
            deduped.append(item)
            if len(deduped) >= top_k:
                break

        return deduped
