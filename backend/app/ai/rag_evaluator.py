from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory

logger = logging.getLogger("memoryverse.rag_evaluator")


class RAGGroundingEvaluator:
    """Automated synthetic probe benchmarking engine evaluating RAG retrieval precision, recall, and groundedness."""

    _history: dict[str, list[dict[str, Any]]] = {}

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
        "does",
        "did",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "my",
        "your",
        "his",
        "her",
        "its",
        "our",
        "their",
        "this",
        "that",
        "these",
        "those",
        "from",
        "as",
    }

    @classmethod
    def _extract_tokens(cls, text: str) -> set[str]:
        tokens = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", text.lower())
        return {t for t in tokens if t not in cls.STOPWORDS}

    @classmethod
    def generate_synthetic_probe(cls, memory: Memory) -> dict[str, str]:
        """Synthesize a natural retrieval probe query from a ground-truth memory."""
        text = memory.content.strip()
        tokens = list(cls._extract_tokens(text))

        # Check for location/work statements
        loc_match = re.search(
            r"\b(?:lives in|moved to|resides in)\s+([a-zA-Z\s]+)", text, re.IGNORECASE
        )
        work_match = re.search(
            r"\b(?:works at|employed at|works for)\s+([a-zA-Z\s]+)", text, re.IGNORECASE
        )
        pref_match = re.search(
            r"\b(?:prefers|likes|uses)\s+([a-zA-Z0-9\s_\-]+)", text, re.IGNORECASE
        )

        if loc_match and work_match:
            loc = loc_match.group(1).strip().split()[0]
            work = work_match.group(1).strip().split()[0]
            query = f"Where does the user live and work ({loc}, {work})?"
        elif loc_match:
            loc = loc_match.group(1).strip().split()[0]
            query = f"Where does the user live in {loc}?"
        elif pref_match:
            pref = pref_match.group(1).strip()
            query = f"What is the user preference regarding {pref}?"
        elif len(tokens) >= 3:
            query = f"Tell me about {' '.join(tokens[:4])}"
        else:
            query = text

        return {
            "probe_id": str(uuid.uuid4()),
            "query": query,
            "ground_truth_memory_id": memory.id,
        }

    @classmethod
    async def run_benchmark(
        cls,
        db: AsyncSession,
        workspace_id: str,
        memories: list[Memory],
        sample_size: int = 5,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Execute automated synthetic probe evaluation across workspace memories."""
        from app.ai.retrieval import HybridSearchEngine

        now_dt = datetime.now(UTC)
        run_id = f"eval_run_{uuid.uuid4().hex[:12]}"

        if not memories:
            empty_result = {
                "workspace_id": workspace_id,
                "run_id": run_id,
                "total_probes": 0,
                "hit_rate": 0.0,
                "mean_reciprocal_rank": 0.0,
                "average_precision": 0.0,
                "average_groundedness": 0.0,
                "overall_score": 0.0,
                "letter_grade": "N/A",
                "probes": [],
                "evaluated_at": now_dt,
            }
            cls._history.setdefault(workspace_id, []).append(empty_result)
            return empty_result

        # Sample memories
        selected_memories = memories[:sample_size]
        probe_results: list[dict[str, Any]] = []

        total_rr = 0.0
        total_hits = 0
        total_precision = 0.0
        total_groundedness = 0.0

        for mem in selected_memories:
            probe = cls.generate_synthetic_probe(mem)
            gt_id = probe["ground_truth_memory_id"]
            query_tokens = cls._extract_tokens(probe["query"])
            gt_tokens = cls._extract_tokens(mem.content)

            # Query retrieval pipeline
            search_res = await HybridSearchEngine.search(
                db=db,
                workspace_id=workspace_id,
                query=probe["query"],
                top_k=top_k,
                include_memories=True,
                include_documents=False,
            )

            retrieved_ids = [m.id for m in search_res]
            hit = gt_id in retrieved_ids
            retrieved_rank = retrieved_ids.index(gt_id) + 1 if hit else None
            rr = (1.0 / retrieved_rank) if hit and retrieved_rank else 0.0

            # Calculate context precision: relevant returned memories / top_k
            relevant_chunks = 0
            retrieved_tokens: set[str] = set()
            for r_mem in search_res:
                r_tokens = cls._extract_tokens(r_mem.content)
                retrieved_tokens.update(r_tokens)
                if r_mem.id == gt_id or (gt_tokens and (r_tokens & gt_tokens)):
                    relevant_chunks += 1

            context_precision = round(relevant_chunks / max(len(search_res), 1), 2)

            # Calculate groundedness: overlap between query/ground-truth tokens and retrieved tokens
            target_tokens = query_tokens | gt_tokens
            groundedness = (
                round(len(target_tokens & retrieved_tokens) / max(len(target_tokens), 1), 2)
                if target_tokens
                else 1.0
            )

            if hit:
                total_hits += 1
            total_rr += rr
            total_precision += context_precision
            total_groundedness += groundedness

            probe_results.append(
                {
                    "probe_id": probe["probe_id"],
                    "query": probe["query"],
                    "ground_truth_memory_id": gt_id,
                    "retrieved_rank": retrieved_rank,
                    "hit": hit,
                    "reciprocal_rank": round(rr, 3),
                    "context_precision": context_precision,
                    "groundedness_score": groundedness,
                }
            )

        n_probes = len(probe_results)
        hit_rate = round(total_hits / max(n_probes, 1), 3)
        mrr = round(total_rr / max(n_probes, 1), 3)
        avg_precision = round(total_precision / max(n_probes, 1), 3)
        avg_groundedness = round(total_groundedness / max(n_probes, 1), 3)

        # Composite score
        overall_score = round(
            0.40 * hit_rate + 0.30 * mrr + 0.15 * avg_precision + 0.15 * avg_groundedness,
            3,
        )

        if overall_score >= 0.88:
            grade = "A+"
        elif overall_score >= 0.78:
            grade = "A"
        elif overall_score >= 0.68:
            grade = "B"
        elif overall_score >= 0.55:
            grade = "C"
        else:
            grade = "Needs Attention"

        result = {
            "workspace_id": workspace_id,
            "run_id": run_id,
            "total_probes": n_probes,
            "hit_rate": hit_rate,
            "mean_reciprocal_rank": mrr,
            "average_precision": avg_precision,
            "average_groundedness": avg_groundedness,
            "overall_score": overall_score,
            "letter_grade": grade,
            "probes": probe_results,
            "evaluated_at": now_dt,
        }

        # Keep last 50 runs per workspace
        ws_hist = cls._history.setdefault(workspace_id, [])
        ws_hist.append(result)
        if len(ws_hist) > 50:
            cls._history[workspace_id] = ws_hist[-50:]

        return result

    @classmethod
    def get_eval_history(cls, workspace_id: str) -> list[dict[str, Any]]:
        """Return historical probe evaluation runs for the specified workspace in reverse chronological order."""
        return list(reversed(cls._history.get(workspace_id, [])))
