from __future__ import annotations

import collections
import logging
import math
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory, MemoryStatus
from app.schemas.chat import (
    UncertaintyCalibrationRequest,
    UncertaintyCalibrationResponse,
)

logger = logging.getLogger("memoryverse.uncertainty_calibrator")


class EpistemicUncertaintyCalibrator:
    """
    Active Continuous Epistemic Uncertainty & Confidence Calibration Engine.
    Disentangles epistemic uncertainty (knowledge deficit from missing evidence)
    from aleatoric uncertainty (inherent ambiguity and conflicting memories),
    evaluating evidence entropy and producing calibrated confidence intervals.
    """

    CONTRADICTION_KEYWORDS = [
        ("enable", "disable"),
        ("allow", "forbid"),
        ("true", "false"),
        ("always", "never"),
        ("secure", "insecure"),
        ("internal", "external"),
        ("encrypt", "plaintext"),
    ]

    @classmethod
    async def calibrate(
        cls,
        db: AsyncSession,
        workspace_id: str,
        request: UncertaintyCalibrationRequest,
    ) -> UncertaintyCalibrationResponse:
        """Calculate calibrated confidence score, uncertainty components, and evidence entropy."""
        now_dt = datetime.now(UTC)

        # 1. Fetch active workspace memories
        stmt = (
            select(Memory)
            .where(
                Memory.workspace_id == workspace_id,
                Memory.status.in_([MemoryStatus.APPROVED, MemoryStatus.PENDING_REVIEW]),
            )
            .limit(100)
        )
        memories = list((await db.execute(stmt)).scalars().all())

        combined_text = f"{request.query} {request.candidate_response}".lower()
        query_words = set(re.findall(r"\b\w{3,}\b", combined_text))

        # 2. Evaluate evidence matching and category distribution
        matching_memories: list[Memory] = []
        best_overlap = 0.0
        category_counts: collections.Counter[str] = collections.Counter()

        for m in memories:
            m_words = set(re.findall(r"\b\w{3,}\b", m.content.lower()))
            if not m_words:
                continue

            overlap = len(query_words & m_words) / float(max(1, len(query_words)))
            if overlap > best_overlap:
                best_overlap = overlap

            if overlap >= 0.15 or len(query_words & m_words) >= 3:
                matching_memories.append(m)
                cat_str = m.category.value if hasattr(m.category, "value") else str(m.category)
                category_counts[cat_str] += 1

        # 3. Calculate Evidence Density & Epistemic Uncertainty
        # Density scales with the relevance of matching memories and lexical overlap
        match_count = len(matching_memories)
        best_match_signal = min(1.0, best_overlap * 1.5)
        coverage_signal = min(1.0, match_count / 2.0)
        density = min(1.0, (best_match_signal * 0.65) + (coverage_signal * 0.35))
        epistemic_uncertainty = max(0.05, round(1.0 - density, 3))

        # 4. Calculate Aleatoric Uncertainty (Conflict & Ambiguity)
        conflict_signals = 0
        if match_count >= 2:
            all_content = " ".join(m.content.lower() for m in matching_memories)
            for w1, w2 in cls.CONTRADICTION_KEYWORDS:
                if w1 in all_content and w2 in all_content:
                    conflict_signals += 1

        aleatoric_uncertainty = min(0.95, round(min(conflict_signals, 3) * 0.25 + 0.10, 3))

        # 5. Calculate Shannon Evidence Entropy
        # H(X) = - sum(p * log2(p)) over memory categories
        total_matched = sum(category_counts.values())
        if total_matched > 1 and len(category_counts) > 1:
            evidence_entropy = round(
                -sum(
                    (count / total_matched) * math.log2(count / total_matched)
                    for count in category_counts.values()
                ),
                3,
            )
        else:
            evidence_entropy = 0.0

        # 6. Calibrated Confidence Score & Confidence Intervals
        raw_calibrated = request.confidence_prior * (
            1.0 - (0.55 * epistemic_uncertainty) - (0.35 * aleatoric_uncertainty)
        )
        calibrated_confidence = round(max(0.05, min(0.99, raw_calibrated)), 3)

        margin = 0.12 * (epistemic_uncertainty + aleatoric_uncertainty)
        confidence_lower = round(max(0.0, calibrated_confidence - margin), 3)
        confidence_upper = round(min(1.0, calibrated_confidence + 0.05), 3)

        # 7. Operational Recommendation
        if calibrated_confidence >= 0.60 and epistemic_uncertainty <= 0.55:
            recommendation = "PROCEED"
        elif aleatoric_uncertainty >= 0.50:
            recommendation = "REQUIRE_HUMAN_DISAMBIGUATION"
        else:
            recommendation = "FLAG_LOW_CONFIDENCE"

        return UncertaintyCalibrationResponse(
            workspace_id=workspace_id,
            query=request.query,
            calibrated_confidence=calibrated_confidence,
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
            epistemic_uncertainty=epistemic_uncertainty,
            aleatoric_uncertainty=aleatoric_uncertainty,
            evidence_entropy=evidence_entropy,
            recommendation=recommendation,
            supporting_memory_count=match_count,
            calibrated_at=now_dt,
        )
