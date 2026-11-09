from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory, MemoryStatus
from app.schemas.search import (
    CrossModalFusionResponse,
    CrossModalSearchRequest,
    FusedMemoryResult,
    ModalScoreBreakdown,
)

logger = logging.getLogger("memoryverse.cross_modal_fusion")


class CrossModalFusionEngine:
    """
    Multi-Modal Cross-Attention Memory Fusion & Synesthetic Retrieval Engine.
    Dynamically weights and synthesizes memory relevance across text, code structures,
    tabular matrices, and audio speech transcripts, producing aligned multi-modal citations.
    """

    CODE_INDICATORS = [
        r"\b(def|class|function|import|return|const|let|var|async|await)\b",
        r"[{}\[\];=><+\-*/]{2,}",
        r"```|\bselect\b.*\bfrom\b|\balembic\b",
    ]

    TABLE_INDICATORS = [
        r"\|.*\|.*\|",
        r"\b(csv|tsv|column|row|header|matrix|dataframe|table)\b",
    ]

    AUDIO_INDICATORS = [
        r"\b(audio|speech|voice|transcript|transcription|recorded|whisper|call\s*log|speaker\s*\d)\b",
    ]

    @classmethod
    def detect_modalities(cls, text: str) -> tuple[str, list[str]]:
        """Identify primary modality and active modality badges for a memory."""
        badges: list[str] = ["TEXT"]
        primary = "text"

        has_code = any(re.search(pat, text, re.IGNORECASE) for pat in cls.CODE_INDICATORS)
        has_table = any(re.search(pat, text, re.IGNORECASE) for pat in cls.TABLE_INDICATORS)
        has_audio = any(re.search(pat, text, re.IGNORECASE) for pat in cls.AUDIO_INDICATORS)

        if has_code:
            badges.append("CODE")
            primary = "code"
        if has_table:
            badges.append("TABLE")
            if not has_code:
                primary = "table"
        if has_audio:
            badges.append("AUDIO")
            if not has_code and not has_table:
                primary = "audio"

        return primary, badges

    @classmethod
    async def search(
        cls,
        db: AsyncSession,
        workspace_id: str,
        request: CrossModalSearchRequest,
    ) -> CrossModalFusionResponse:
        """Execute multi-modal cross-attention fusion search over workspace memories."""
        now_dt = datetime.now(UTC)

        stmt = (
            select(Memory)
            .where(
                Memory.workspace_id == workspace_id,
                Memory.status.in_([MemoryStatus.APPROVED, MemoryStatus.PENDING_REVIEW]),
            )
            .limit(150)
        )
        memories = list((await db.execute(stmt)).scalars().all())

        query_words = set(re.findall(r"\b\w{3,}\b", request.query.lower()))
        fused_items: list[FusedMemoryResult] = []
        modality_distribution: dict[str, int] = {"text": 0, "code": 0, "table": 0, "audio": 0}

        total_weight = max(
            0.01,
            request.text_weight + request.code_weight + request.table_weight + request.audio_weight,
        )
        norm_text_w = request.text_weight / total_weight
        norm_code_w = request.code_weight / total_weight
        norm_table_w = request.table_weight / total_weight
        norm_audio_w = request.audio_weight / total_weight

        for m in memories:
            content_lower = m.content.lower()
            m_words = set(re.findall(r"\b\w{3,}\b", content_lower))
            overlap_words = query_words & m_words
            lexical_ratio = len(overlap_words) / float(max(1, len(query_words)))

            primary_mod, badges = cls.detect_modalities(m.content)
            modality_distribution[primary_mod] = modality_distribution.get(primary_mod, 0) + 1

            # Compute modal-specific affinity scores
            base_score = min(1.0, lexical_ratio * 1.5)
            code_affinity = min(1.0, base_score * 1.25) if "CODE" in badges else base_score * 0.40
            table_affinity = min(1.0, base_score * 1.20) if "TABLE" in badges else base_score * 0.35
            audio_affinity = min(1.0, base_score * 1.30) if "AUDIO" in badges else base_score * 0.30
            text_affinity = base_score

            fused_score = round(
                min(
                    0.99,
                    (text_affinity * norm_text_w)
                    + (code_affinity * norm_code_w)
                    + (table_affinity * norm_table_w)
                    + (audio_affinity * norm_audio_w),
                ),
                3,
            )

            # Matched aspect keywords
            aspects = list(overlap_words)[:5]

            breakdown = ModalScoreBreakdown(
                text_score=round(text_affinity, 3),
                code_score=round(code_affinity, 3),
                tabular_score=round(table_affinity, 3),
                audio_score=round(audio_affinity, 3),
            )

            fused_items.append(
                FusedMemoryResult(
                    memory_id=m.id,
                    content=m.content,
                    category=m.category.value if hasattr(m.category, "value") else str(m.category),
                    primary_modality=primary_mod,
                    fused_score=fused_score,
                    modal_scores=breakdown,
                    modality_badges=badges,
                    matched_aspects=aspects,
                )
            )

        # Sort by fused score descending
        fused_items.sort(key=lambda x: x.fused_score, reverse=True)
        top_results = fused_items[: request.top_k]

        alignment_score = (
            round(sum(r.fused_score for r in top_results) / float(len(top_results)), 3)
            if top_results
            else 0.50
        )

        return CrossModalFusionResponse(
            workspace_id=workspace_id,
            query=request.query,
            total_candidates_evaluated=len(memories),
            cross_modal_alignment_score=alignment_score,
            modality_distribution=modality_distribution,
            results=top_results,
            executed_at=now_dt,
        )
