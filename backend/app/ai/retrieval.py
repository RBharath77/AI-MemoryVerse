import math
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import get_embedding_provider
from app.models.document import Document, DocumentChunk
from app.models.memory import Memory, MemoryStatus


@dataclass
class SearchResultItem:
    source_type: str  # "memory" or "document"
    id: str
    title: str
    content: str
    score: float
    category: str | None = None
    section_title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def cosine_similarity(vec_a: list[float] | None, vec_b: list[float] | None) -> float:
    """Compute cosine similarity between two vector lists."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a, b in zip(vec_a, vec_b)))  # or sum(a*a)
    norm_b = math.sqrt(sum(b * b for a, b in zip(vec_a, vec_b)))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class HybridSearchEngine:
    """Performs multi-tier retrieval combining keyword and vector similarity with RRF."""

    @classmethod
    async def search(
        cls,
        db: AsyncSession,
        workspace_id: str,
        query: str,
        top_k: int = 10,
        filter_category: str | None = None,
        include_documents: bool = True,
        include_memories: bool = True,
    ) -> list[SearchResultItem]:
        if not query or not query.strip():
            return []

        embedder = get_embedding_provider()
        try:
            query_embedding = await embedder.get_embedding(query.strip())
        except Exception:
            query_embedding = None

        query_terms = [t.lower() for t in query.strip().split() if len(t) >= 2]

        all_candidates: dict[str, SearchResultItem] = {}
        vector_ranked: list[str] = []
        keyword_ranked: list[str] = []

        # 1. Retrieve Memories
        if include_memories:
            mem_q = select(Memory).where(
                Memory.workspace_id == workspace_id,
                Memory.status == MemoryStatus.APPROVED,
            )
            if filter_category:
                mem_q = mem_q.where(Memory.category == filter_category)

            memories = (await db.execute(mem_q)).scalars().all()

            for mem in memories:
                item_key = f"memory_{mem.id}"
                content_lower = mem.content.lower()

                # Keyword match score
                kw_matches = sum(1 for term in query_terms if term in content_lower)
                kw_score = kw_matches / len(query_terms) if query_terms else 0.0

                # Vector similarity score
                vec_score = 0.0
                if query_embedding and mem.embedding:
                    vec_score = cosine_similarity(query_embedding, mem.embedding)

                item = SearchResultItem(
                    source_type="memory",
                    id=mem.id,
                    title=f"Memory ({mem.category.value})",
                    content=mem.content,
                    score=max(kw_score, vec_score),
                    category=mem.category.value,
                    metadata={
                        "importance": mem.importance,
                        "is_pinned": mem.is_pinned,
                        "tags": mem.tags,
                        "kw_score": round(kw_score, 4),
                        "vec_score": round(vec_score, 4),
                    },
                )
                all_candidates[item_key] = item

                if kw_score > 0:
                    keyword_ranked.append((item_key, kw_score))
                if vec_score > 0.3:
                    vector_ranked.append((item_key, vec_score))

        # 2. Retrieve Document Chunks
        if include_documents:
            chunk_q = (
                select(DocumentChunk, Document.title)
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(DocumentChunk.workspace_id == workspace_id)
            )
            chunk_rows = (await db.execute(chunk_q)).all()

            for chunk, doc_title in chunk_rows:
                item_key = f"chunk_{chunk.id}"
                content_lower = chunk.content.lower()

                kw_matches = sum(1 for term in query_terms if term in content_lower)
                kw_score = kw_matches / len(query_terms) if query_terms else 0.0

                vec_score = 0.0
                if query_embedding and chunk.embedding:
                    vec_score = cosine_similarity(query_embedding, chunk.embedding)

                sec = chunk.section_title or f"Chunk #{chunk.chunk_index + 1}"
                item = SearchResultItem(
                    source_type="document",
                    id=chunk.id,
                    title=f"{doc_title} (Section: {sec})",
                    content=chunk.content,
                    score=max(kw_score, vec_score),
                    section_title=chunk.section_title,
                    metadata={
                        "document_id": chunk.document_id,
                        "chunk_index": chunk.chunk_index,
                        "token_count": chunk.token_count,
                        "kw_score": round(kw_score, 4),
                        "vec_score": round(vec_score, 4),
                    },
                )
                all_candidates[item_key] = item

                if kw_score > 0:
                    keyword_ranked.append((item_key, kw_score))
                if vec_score > 0.3:
                    vector_ranked.append((item_key, vec_score))

        # 3. Reciprocal Rank Fusion (RRF)
        # Sort ranks descending
        keyword_sorted = [k for k, _ in sorted(keyword_ranked, key=lambda x: x[1], reverse=True)]
        vector_sorted = [k for k, _ in sorted(vector_ranked, key=lambda x: x[1], reverse=True)]

        rrf_scores: dict[str, float] = {}
        k_smooth = 60.0

        for rank, key in enumerate(keyword_sorted):
            rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (k_smooth + rank + 1))

        for rank, key in enumerate(vector_sorted):
            rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (k_smooth + rank + 1))

        # Assign composite score to candidates
        scored_results: list[SearchResultItem] = []
        for key, rrf_score in rrf_scores.items():
            if key in all_candidates:
                candidate = all_candidates[key]
                candidate.score = round(rrf_score, 5)
                scored_results.append(candidate)

        # Fallback if no RRF matches (e.g. very short query)
        if not scored_results and all_candidates:
            scored_results = sorted(
                all_candidates.values(),
                key=lambda x: x.metadata.get("vec_score", 0.0),
                reverse=True,
            )

        scored_results.sort(key=lambda x: x.score, reverse=True)
        return scored_results[:top_k]
