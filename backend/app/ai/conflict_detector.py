import re
from dataclasses import dataclass


@dataclass
class ConflictResult:
    is_conflict: bool
    conflicting_memory_id: str | None = None
    conflict_type: str = "none"  # "direct_contradiction", "superseding_update", "none"
    explanation: str = ""


@dataclass
class DuplicateResult:
    is_duplicate: bool
    duplicate_memory_id: str | None = None
    similarity_score: float = 0.0


class ConflictDetector:
    """Detects duplicates and contradictions between candidate facts and existing memories."""

    # Common antonym / contradiction patterns for preferences and states
    ANTONYM_PAIRS = [
        (r"\b(prefer|love|like|enjoy)\b", r"\b(hate|dislike|avoid|never use)\b"),
        (r"\b(dark mode|dark theme)\b", r"\b(light mode|light theme)\b"),
        (r"\b(mac|macos|apple)\b", r"\b(windows|linux)\b"),
        (r"\b(remote|work from home)\b", r"\b(in-office|onsite|relocated to office)\b"),
        (r"\b(single)\b", r"\b(married|in a relationship)\b"),
        (
            r"\b(lives in|moved to|relocated to)\s+([a-zA-Z\s]+)",
            r"\b(lives in|moved to|relocated to)\s+([a-zA-Z\s]+)",
        ),
    ]

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", "", text)
        return re.sub(r"\s+", " ", text)

    @classmethod
    def check_duplicate(
        cls,
        candidate_text: str,
        existing_memories: list[dict],  # list of dicts with {"id": str, "content": str}
        threshold: float = 0.85,
    ) -> DuplicateResult:
        norm_candidate = cls._normalize(candidate_text)
        cand_tokens = set(norm_candidate.split())

        if not cand_tokens:
            return DuplicateResult(is_duplicate=False)

        for mem in existing_memories:
            norm_existing = cls._normalize(mem["content"])
            # Exact match
            if norm_candidate == norm_existing:
                return DuplicateResult(
                    is_duplicate=True,
                    duplicate_memory_id=mem["id"],
                    similarity_score=1.0,
                )

            # Token-based Jaccard similarity
            ex_tokens = set(norm_existing.split())
            if not ex_tokens:
                continue

            intersection = cand_tokens.intersection(ex_tokens)
            union = cand_tokens.union(ex_tokens)
            jaccard = len(intersection) / len(union) if union else 0.0

            if jaccard >= threshold:
                return DuplicateResult(
                    is_duplicate=True,
                    duplicate_memory_id=mem["id"],
                    similarity_score=round(jaccard, 3),
                )

        return DuplicateResult(is_duplicate=False)

    @classmethod
    def check_contradiction(
        cls,
        candidate_text: str,
        existing_memories: list[
            dict
        ],  # list of dicts with {"id": str, "content": str, "category": str}
    ) -> ConflictResult:
        cand_lower = candidate_text.lower()

        for mem in existing_memories:
            ex_lower = mem["content"].lower()

            # Rule 1: Preference reversals (e.g. loves X vs hates X)
            for pos_pat, neg_pat in cls.ANTONYM_PAIRS[:1]:
                has_pos_cand = bool(re.search(pos_pat, cand_lower))
                has_neg_cand = bool(re.search(neg_pat, cand_lower))
                has_pos_ex = bool(re.search(pos_pat, ex_lower))
                has_neg_ex = bool(re.search(neg_pat, ex_lower))

                # Check shared target entity
                cand_words = set(cls._normalize(candidate_text).split())
                ex_words = set(cls._normalize(mem["content"]).split())
                shared = cand_words.intersection(ex_words)

                if len(shared) >= 2:
                    if (has_pos_cand and has_neg_ex) or (has_neg_cand and has_pos_ex):
                        m_content = mem["content"]
                        return ConflictResult(
                            is_conflict=True,
                            conflicting_memory_id=mem["id"],
                            conflict_type="direct_contradiction",
                            explanation=f"Conflicting sentiment regarding subject: '{m_content}'",
                        )

            # Rule 2: Theme / Mode conflicts (dark vs light mode)
            if ("dark mode" in cand_lower or "dark theme" in cand_lower) and (
                "light mode" in ex_lower or "light theme" in ex_lower
            ):
                return ConflictResult(
                    is_conflict=True,
                    conflicting_memory_id=mem["id"],
                    conflict_type="direct_contradiction",
                    explanation="Contradicts existing preference (dark mode vs light mode).",
                )
            if ("light mode" in cand_lower or "light theme" in cand_lower) and (
                "dark mode" in ex_lower or "dark theme" in ex_lower
            ):
                return ConflictResult(
                    is_conflict=True,
                    conflicting_memory_id=mem["id"],
                    conflict_type="direct_contradiction",
                    explanation="Contradicts existing preference (light mode vs dark mode).",
                )

            # Rule 3: Relocation / Location change (e.g. "moved to Paris" vs "lives in London")
            loc_match_cand = re.search(
                r"\b(?:lives in|moved to|relocated to)\s+([a-zA-Z\s]+)", cand_lower
            )
            loc_match_ex = re.search(
                r"\b(?:lives in|moved to|relocated to)\s+([a-zA-Z\s]+)", ex_lower
            )
            if loc_match_cand and loc_match_ex:
                loc_cand = loc_match_cand.group(1).strip()
                loc_ex = loc_match_ex.group(1).strip()
                if loc_cand != loc_ex:
                    return ConflictResult(
                        is_conflict=True,
                        conflicting_memory_id=mem["id"],
                        conflict_type="superseding_update",
                        explanation=(
                            f"Location change detected: candidate indicates '{loc_cand}', "
                            f"but previous record indicates '{loc_ex}'."
                        ),
                    )

        return ConflictResult(is_conflict=False)
