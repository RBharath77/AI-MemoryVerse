from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.retrieval import HybridSearchEngine
from app.schemas.search import (
    DecomposedSearchRequest,
    DecomposedSearchResponse,
    SearchResultResponseItem,
    SubQueryExecutionResult,
    SubQueryItem,
)

logger = logging.getLogger("memoryverse.query_decomposer")


class QueryDecompositionEngine:
    """
    Semantic Query Decomposition & Multi-Step Sub-Query Planning Engine.
    Breaks compound, comparative, and multi-faceted inquiries into atomic sub-queries,
    executes parallel retrieval, and fuses context with aspect attribution.
    """

    CONJUNCTION_PATTERNS = [
        r"\s+and\s+",
        r"\s+vs\.?\s+",
        r"\s+versus\s+",
        r"\s+compared\s+to\s+",
        r"\s+as\s+well\s+as\s+",
        r"\s+in\s+addition\s+to\s+",
        r"\s*;\s*",
        r"\s+while\s+",
        r"\s+along\s+with\s+",
    ]

    @classmethod
    def decompose_query(cls, query: str, max_sub_queries: int = 4) -> list[SubQueryItem]:
        """
        Decompose a compound natural language prompt into atomic, targeted sub-queries.
        """
        cleaned = query.strip()
        sub_query_strings: list[str] = []

        # 1. Check for comparative structure ("compare X to Y", "difference between X and Y")
        compare_match = re.search(
            r"(?:compare|difference\s+between)\s+(.+?)\s+(?:and|to|with)\s+(.+)",
            cleaned,
            re.IGNORECASE,
        )
        if compare_match:
            part_a = compare_match.group(1).strip()
            part_b = compare_match.group(2).strip().rstrip("?.")
            sub_query_strings.append(part_a)
            sub_query_strings.append(part_b)
            sub_query_strings.append(f"comparison between {part_a} and {part_b}")
        else:
            # 2. Split on common conjunction patterns
            combined_pattern = "|".join(cls.CONJUNCTION_PATTERNS)
            parts = re.split(combined_pattern, cleaned, flags=re.IGNORECASE)
            for part in parts:
                candidate = part.strip().rstrip("?.")
                if len(candidate) >= 4 and candidate.lower() not in [
                    "what",
                    "how",
                    "why",
                    "which",
                    "is",
                    "are",
                ]:
                    sub_query_strings.append(candidate)

        # Fallback if no clean split or only 1 short string
        if not sub_query_strings or len(sub_query_strings) == 1:
            sub_query_strings = [cleaned]

        sub_queries: list[SubQueryItem] = []
        for idx, sq_text in enumerate(sub_query_strings[:max_sub_queries]):
            # Infer aspect based on keywords
            sq_lower = sq_text.lower()
            if any(k in sq_lower for k in ["security", "auth", "encrypt", "token", "guard", "dlp"]):
                aspect = "security"
            elif any(
                k in sq_lower for k in ["cache", "latency", "speed", "performance", "throughput"]
            ):
                aspect = "performance"
            elif any(
                k in sq_lower
                for k in ["architecture", "model", "schema", "database", "orm", "fastapi"]
            ):
                aspect = "architecture"
            elif any(k in sq_lower for k in ["compare", "versus", "difference", "tradeoff"]):
                aspect = "comparison"
            elif any(k in sq_lower for k in ["policy", "compliance", "retention", "gdpr", "audit"]):
                aspect = "compliance"
            else:
                aspect = f"aspect_{idx + 1}"

            sub_queries.append(
                SubQueryItem(
                    sub_query_id=f"sq_{idx + 1}_{str(uuid.uuid4())[:8]}",
                    sub_query=sq_text,
                    aspect=aspect,
                    priority=idx + 1,
                )
            )

        return sub_queries

    @classmethod
    async def decompose_and_search(
        cls,
        db: AsyncSession,
        workspace_id: str,
        request: DecomposedSearchRequest,
    ) -> DecomposedSearchResponse:
        """
        Decomposes query, runs parallel hybrid search for each aspect,
        fuses candidates, and synthesizes a structured contextual briefing.
        """
        now_dt = datetime.now(UTC)
        sub_queries = cls.decompose_query(request.query, max_sub_queries=request.max_sub_queries)

        executions: list[SubQueryExecutionResult] = []
        fused_dict: dict[str, SearchResultResponseItem] = {}
        subquery_match_counts: dict[str, int] = {}

        # 1. Execute retrieval per sub-query
        for sq in sub_queries:
            raw_results = await HybridSearchEngine.search(
                db=db,
                workspace_id=workspace_id,
                query=sq.sub_query,
                top_k=request.top_k_per_sub_query,
                include_documents=request.include_documents,
                include_memories=request.include_memories,
            )

            response_items = [
                SearchResultResponseItem(
                    source_type=r.source_type,
                    id=r.id,
                    title=r.title,
                    content=r.content,
                    score=r.score,
                    category=r.category,
                    section_title=r.section_title,
                    metadata=r.metadata or {},
                )
                for r in raw_results
            ]

            executions.append(
                SubQueryExecutionResult(
                    sub_query_id=sq.sub_query_id,
                    sub_query=sq.sub_query,
                    aspect=sq.aspect,
                    matches_found=len(response_items),
                    results=response_items,
                )
            )

            # 2. Track candidates for rank fusion & cross-subquery boosting
            for item in response_items:
                subquery_match_counts[item.id] = subquery_match_counts.get(item.id, 0) + 1
                if item.id not in fused_dict:
                    fused_dict[item.id] = item
                else:
                    # Keep max base score
                    if item.score > fused_dict[item.id].score:
                        fused_dict[item.id].score = item.score

        # 3. Apply multi-aspect occurrence boost
        for item_id, item in fused_dict.items():
            overlap_count = subquery_match_counts.get(item_id, 1)
            if overlap_count > 1:
                boost = 0.10 * (overlap_count - 1)
                item.score = min(1.0, round(item.score + boost, 4))

        fused_list = sorted(fused_dict.values(), key=lambda x: x.score, reverse=True)

        # 4. Generate structured synthesis briefing
        briefing_lines: list[str] = [
            f"### Query Decomposition Synthesis for: '{request.query}'",
            f"Decomposed into {len(sub_queries)} atomic sub-goals across aspects: {', '.join(sq.aspect for sq in sub_queries)}.",
            "",
        ]

        for exec_res in executions:
            briefing_lines.append(
                f"#### Sub-Query: '{exec_res.sub_query}' (Aspect: `{exec_res.aspect}`)"
            )
            if exec_res.results:
                top_titles = [f"• {r.title} (score: {r.score:.3f})" for r in exec_res.results[:3]]
                briefing_lines.extend(top_titles)
            else:
                briefing_lines.append("• No direct records identified for this sub-query.")
            briefing_lines.append("")

        briefing_text = "\n".join(briefing_lines)

        return DecomposedSearchResponse(
            original_query=request.query,
            sub_queries=sub_queries,
            sub_query_executions=executions,
            fused_results=fused_list,
            synthesis_briefing=briefing_text,
            total_unique_sources=len(fused_list),
            executed_at=now_dt,
        )
