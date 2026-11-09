from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory, MemoryStatus
from app.schemas.chat import (
    AttributionVerificationRequest,
    AttributionVerificationResponse,
    ClaimAttributionResult,
)

logger = logging.getLogger("memoryverse.attribution_verifier")


class GroundingAttributionVerifier:
    """
    Semantic Knowledge Grounding & Hallucination Attribution Verifier.
    Audits generated assistant responses and documents against retrieved workspace memories,
    deconstructing text into atomic factual claims, verifying premise entailment,
    and calculating grounding fidelity and hallucination risk indices.
    """

    CONTRADICTION_PAIRS = [
        ("allow", "forbid"),
        ("allowed", "forbidden"),
        ("enable", "disable"),
        ("enabled", "disabled"),
        ("true", "false"),
        ("always", "never"),
        ("secure", "insecure"),
        ("async", "synchronous"),
        ("encrypted", "plaintext"),
    ]

    @classmethod
    def extract_claims(cls, text: str) -> list[str]:
        """Split generated prose into atomic factual propositions."""
        # Split on sentence boundaries and bullet points
        raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
        claims: list[str] = []
        for s in raw_sentences:
            cleaned = s.strip().lstrip("•-* ").strip()
            # Ignore greetings, short fragments, or pure conversational transitions
            if len(cleaned.split()) >= 4 and not cleaned.lower().startswith(
                ("hello", "hi ", "sure,", "here is", "in summary", "thank you", "hope this helps")
            ):
                claims.append(cleaned)

        if not claims and text.strip():
            claims = [text.strip()]
        return claims

    @classmethod
    async def verify(
        cls,
        db: AsyncSession,
        workspace_id: str,
        request: AttributionVerificationRequest,
    ) -> AttributionVerificationResponse:
        """
        Audit generated text against grounding sources or workspace memories.
        """
        now_dt = datetime.now(UTC)
        claims_text = cls.extract_claims(request.generated_text)

        # 1. Resolve grounding context
        grounding_texts: list[tuple[str, str]] = []  # (source_id, source_content)
        if request.grounding_sources:
            for idx, src in enumerate(request.grounding_sources):
                s_id = str(src.get("id") or src.get("source_id") or f"src_{idx + 1}")
                s_text = str(src.get("content") or src.get("text") or "")
                if s_text:
                    grounding_texts.append((s_id, s_text))
        else:
            # Query active workspace memories to verify against
            stmt = (
                select(Memory)
                .where(
                    Memory.workspace_id == workspace_id,
                    Memory.status.in_([MemoryStatus.APPROVED, MemoryStatus.PENDING_REVIEW]),
                )
                .limit(100)
            )
            memories = list((await db.execute(stmt)).scalars().all())
            for m in memories:
                grounding_texts.append((m.id, m.content))

        # 2. Verify each claim
        claim_results: list[ClaimAttributionResult] = []
        supported_count = 0
        contradicted_count = 0
        ungrounded_count = 0

        for idx, claim in enumerate(claims_text):
            claim_lower = claim.lower()
            claim_words = set(re.findall(r"\b\w{3,}\b", claim_lower))

            best_match_id: str | None = None
            best_overlap = 0.0
            is_contradiction = False
            contradiction_reason: str | None = None

            for s_id, s_text in grounding_texts:
                src_lower = s_text.lower()
                src_words = set(re.findall(r"\b\w{3,}\b", src_lower))

                if not claim_words or not src_words:
                    continue

                overlap = len(claim_words & src_words) / float(len(claim_words))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_match_id = s_id

                # Check contradiction pairs
                for term_a, term_b in cls.CONTRADICTION_PAIRS:
                    if (term_a in claim_lower and term_b in src_lower) or (
                        term_b in claim_lower and term_a in src_lower
                    ):
                        # If shared topic words exist, flag contradiction
                        if len(claim_words & src_words) >= 2:
                            is_contradiction = True
                            contradiction_reason = (
                                f"Polarity mismatch: claim uses '{term_a if term_a in claim_lower else term_b}' "
                                f"while source {s_id} asserts '{term_b if term_a in claim_lower else term_a}'."
                            )
                            best_match_id = s_id
                            break
                if is_contradiction:
                    break

            # 3. Classify claim status
            threshold = request.strictness * 0.40  # normalized threshold
            if is_contradiction:
                status = "CONTRADICTED"
                confidence = 0.90
                contradicted_count += 1
                supporting = [best_match_id] if best_match_id else []
            elif best_overlap >= threshold:
                status = "SUPPORTED"
                confidence = min(0.99, round(0.60 + best_overlap * 0.40, 2))
                supported_count += 1
                supporting = [best_match_id] if best_match_id else []
            else:
                status = "UNGROUNDED"
                confidence = round(1.0 - best_overlap, 2)
                ungrounded_count += 1
                supporting = []

            claim_results.append(
                ClaimAttributionResult(
                    claim_index=idx + 1,
                    claim_text=claim,
                    status=status,
                    confidence=confidence,
                    supporting_sources=supporting,
                    contradiction_detail=contradiction_reason,
                )
            )

        total_claims = max(1, len(claim_results))
        fidelity = round(supported_count / float(total_claims), 3)
        risk = round(
            min(1.0, (ungrounded_count * 0.7 + contradicted_count * 1.0) / float(total_claims)),
            3,
        )
        is_grounded = fidelity >= 0.60 and contradicted_count == 0

        return AttributionVerificationResponse(
            workspace_id=workspace_id,
            total_claims=len(claim_results),
            supported_claims=supported_count,
            contradicted_claims=contradicted_count,
            ungrounded_claims=ungrounded_count,
            grounding_fidelity_score=fidelity,
            hallucination_risk_index=risk,
            is_grounded=is_grounded,
            claims=claim_results,
            verified_at=now_dt,
        )
