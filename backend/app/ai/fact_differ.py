from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class SemanticFactDiff:
    old_content: str
    new_content: str
    similarity_score: float
    added_tokens: list[str] = field(default_factory=list)
    removed_tokens: list[str] = field(default_factory=list)
    contradicted_entities: list[str] = field(default_factory=list)
    temporal_shift_summary: str = ""


class SemanticFactDiffer:
    """Computes fine-grained semantic fact-level diffs between conflicting

    or evolving memory statements. Identifies added and removed attributes,
    contradiction entities, and produces a structured temporal delta.
    """

    STOP_WORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "in",
        "into",
        "is",
        "it",
        "no",
        "not",
        "of",
        "on",
        "or",
        "such",
        "that",
        "the",
        "their",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "was",
        "will",
        "with",
    }

    CONTRADICTION_PATTERNS = [
        # Location change: lives in X vs moved to Y
        (
            r"\b(?:lives in|resides in|moved to|relocated to)\s+([a-zA-Z\s]+?)(?:\s+(?:and|who|with|at|for)\b|$)",
            r"\b(?:lives in|resides in|moved to|relocated to)\s+([a-zA-Z\s]+?)(?:\s+(?:and|who|with|at|for)\b|$)",
            "Location",
        ),
        # Theme / mode: dark mode vs light mode
        (
            r"\b(dark mode|dark theme)\b",
            r"\b(light mode|light theme)\b",
            "Theme preference",
        ),
        # Platform: macOS / Apple vs Windows / Linux
        (
            r"\b(mac|macos|apple|ios)\b",
            r"\b(windows|linux|android|pc)\b",
            "Platform preference",
        ),
        # Work arrangement: remote vs onsite / in-office
        (
            r"\b(remote|work from home|wfh)\b",
            r"\b(in-office|onsite|office|hybrid)\b",
            "Work arrangement",
        ),
        # Marital / Relationship status
        (
            r"\b(single|unmarried)\b",
            r"\b(married|in a relationship|engaged)\b",
            "Relationship status",
        ),
        # Sentiment / affinity: loves / prefers vs hates / dislikes
        (
            r"\b(prefer|love|loves|enjoy|enjoys|favorite)\b",
            r"\b(hate|hates|dislike|dislikes|avoid|avoids)\b",
            "Sentiment orientation",
        ),
    ]

    @classmethod
    def _tokenize(cls, text: str) -> list[str]:
        cleaned = re.sub(r"[^\w\s]", "", text.lower()).strip()
        tokens = [w for w in cleaned.split() if w and w not in cls.STOP_WORDS]
        return tokens

    @classmethod
    def compute_diff(cls, old_content: str, new_content: str) -> SemanticFactDiff:
        old_clean = (old_content or "").strip()
        new_clean = (new_content or "").strip()

        old_tokens = cls._tokenize(old_clean)
        new_tokens = cls._tokenize(new_clean)

        old_set = set(old_tokens)
        new_set = set(new_tokens)

        added = sorted(list(new_set - old_set))
        removed = sorted(list(old_set - new_set))

        # Jaccard Token Similarity
        union = old_set | new_set
        similarity = round(len(old_set & new_set) / max(len(union), 1), 3)

        # Detect specific semantic contradiction pairs
        contradicted: list[str] = []
        old_lower = old_clean.lower()
        new_lower = new_clean.lower()

        for pat1, pat2, category in cls.CONTRADICTION_PATTERNS:
            m1_old = re.search(pat1, old_lower)
            m2_new = re.search(pat2, new_lower)
            if m1_old and m2_new:
                val_old = m1_old.group(1).strip() if m1_old.groups() else m1_old.group(0).strip()
                val_new = m2_new.group(1).strip() if m2_new.groups() else m2_new.group(0).strip()
                if val_old != val_new:
                    contradicted.append(f"{category}: '{val_old}' -> '{val_new}'")
                continue

            m2_old = re.search(pat2, old_lower)
            m1_new = re.search(pat1, new_lower)
            if m2_old and m1_new:
                val_old = m2_old.group(1).strip() if m2_old.groups() else m2_old.group(0).strip()
                val_new = m1_new.group(1).strip() if m1_new.groups() else m1_new.group(0).strip()
                if val_old != val_new:
                    contradicted.append(f"{category}: '{val_old}' -> '{val_new}'")

        # Generate human-readable temporal summary
        if contradicted:
            summary = (
                f"Contradictory state detected ({'; '.join(contradicted)}). "
                f"Newer record represents an updated state or preference reversal."
            )
        elif added and removed:
            summary = (
                f"Semantic modification: replaced previous attributes ({', '.join(removed[:3])}) "
                f"with updated details ({', '.join(added[:3])})."
            )
        elif added:
            summary = (
                f"Incremental fact addition: expanded context with {len(added)} new attributes."
            )
        elif removed:
            summary = f"Fact pruning: streamlined context by removing {len(removed)} attributes."
        else:
            summary = "Semantically equivalent phrasing without substantive factual deviation."

        return SemanticFactDiff(
            old_content=old_clean,
            new_content=new_clean,
            similarity_score=similarity,
            added_tokens=added,
            removed_tokens=removed,
            contradicted_entities=contradicted,
            temporal_shift_summary=summary,
        )
