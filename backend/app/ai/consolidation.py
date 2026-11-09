from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.memory import Memory


@dataclass
class MemoryCluster:
    topic: str
    memories: list[Memory]
    extracted_keywords: list[str] = field(default_factory=list)


@dataclass
class SynthesizedClusterData:
    topic: str
    source_memory_ids: list[str]
    synthesized_content: str
    confidence: float
    compression_ratio: float
    source_categories: list[str] = field(default_factory=list)


class MemoryConsolidationEngine:
    """Consolidation engine that abstracts granular episodic memories into high-level semantic principles."""

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
        "user",
        "prefers",
        "likes",
        "uses",
        "works",
        "always",
        "often",
        "daily",
    }

    @classmethod
    def extract_keywords(cls, text: str) -> list[str]:
        """Extract meaningful normalized tokens for semantic topic clustering."""
        tokens = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", text.lower())
        return [t for t in tokens if t not in cls.STOPWORDS]

    @classmethod
    def identify_topic(cls, memories: list[Memory]) -> tuple[str, list[str]]:
        """Identify dominant topic and shared keywords across a cluster of memories."""
        all_tags: list[str] = []
        token_freq: dict[str, int] = {}

        for m in memories:
            if m.tags:
                all_tags.extend([t.lower() for t in m.tags if isinstance(t, str)])
            for kw in cls.extract_keywords(m.content):
                token_freq[kw] = token_freq.get(kw, 0) + 1

        # Prefer shared explicit tags if present
        if all_tags:
            tag_freq: dict[str, int] = {}
            for t in all_tags:
                tag_freq[t] = tag_freq.get(t, 0) + 1
            sorted_tags = sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)
            if sorted_tags[0][1] >= 2:
                top_topic = sorted_tags[0][0].capitalize()
                top_kws = [
                    k for k, _ in sorted(token_freq.items(), key=lambda x: x[1], reverse=True)[:5]
                ]
                return top_topic, top_kws

        # Fallback to highest frequency keyword
        sorted_kws = sorted(token_freq.items(), key=lambda x: x[1], reverse=True)
        if sorted_kws:
            top_kw = sorted_kws[0][0]
            top_kws = [k for k, _ in sorted_kws[:5]]
            return top_kw.capitalize(), top_kws

        return "General", []

    @classmethod
    def cluster_memories(
        cls,
        memories: list[Memory],
        min_memories: int = 2,
        target_topic: str | None = None,
    ) -> list[MemoryCluster]:
        """Cluster active memories by shared topic, tags, or domain keywords."""
        if len(memories) < min_memories:
            return []

        # Group by explicit tags first
        tag_buckets: dict[str, list[Memory]] = {}
        unbucketed: list[Memory] = []

        for m in memories:
            matched = False
            if m.tags:
                for t in m.tags:
                    if isinstance(t, str) and len(t) > 2:
                        norm_tag = t.lower()
                        if target_topic and target_topic.lower() != norm_tag:
                            continue
                        tag_buckets.setdefault(norm_tag, []).append(m)
                        matched = True
                        break
            if not matched:
                unbucketed.append(m)

        # Keyword clustering for unbucketed memories
        kw_buckets: dict[str, list[Memory]] = {}
        for m in unbucketed:
            kws = cls.extract_keywords(m.content)
            for kw in kws[:3]:  # Top 3 salient keywords
                if target_topic and target_topic.lower() != kw:
                    continue
                kw_buckets.setdefault(kw, []).append(m)
                break

        # Combine buckets, deduping memories within clusters
        clusters: list[MemoryCluster] = []
        seen_memory_ids: set[str] = set()

        for group_dict in (tag_buckets, kw_buckets):
            for raw_topic, group in group_dict.items():
                unique_mems = [m for m in group if m.id not in seen_memory_ids]
                # If unique_mems is smaller than min_memories, include shared if total meets min
                mem_list = group if len(unique_mems) < min_memories else unique_mems
                if len(mem_list) >= min_memories:
                    topic, top_kws = cls.identify_topic(mem_list)
                    clusters.append(
                        MemoryCluster(
                            topic=topic,
                            memories=mem_list,
                            extracted_keywords=top_kws,
                        )
                    )
                    for m in mem_list:
                        seen_memory_ids.add(m.id)

        # If target_topic specified but no cluster met min_memories, try matching all memories containing topic
        if target_topic and not clusters:
            topic_lower = target_topic.lower()
            matched_mems = [
                m
                for m in memories
                if topic_lower in m.content.lower()
                or (m.tags and any(topic_lower in str(t).lower() for t in m.tags))
            ]
            if len(matched_mems) >= min_memories:
                clusters.append(
                    MemoryCluster(
                        topic=target_topic.capitalize(),
                        memories=matched_mems,
                        extracted_keywords=cls.extract_keywords(
                            " ".join(m.content for m in matched_mems)
                        )[:5],
                    )
                )

        return clusters

    @classmethod
    def synthesize_cluster(cls, cluster: MemoryCluster) -> SynthesizedClusterData:
        """Synthesize a cluster of granular episodic memories into a high-level semantic statement."""
        source_ids = [m.id for m in cluster.memories]
        source_categories = list(
            {
                m.category.value if hasattr(m.category, "value") else str(m.category)
                for m in cluster.memories
            }
        )

        # Calculate average confidence
        confidences = [m.confidence for m in cluster.memories if m.confidence is not None]
        avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 1.0

        # Calculate total original tokens/words
        total_orig_length = sum(len(m.content.split()) for m in cluster.memories)

        # Synthesize consolidated principle
        # Cleanly abstract sentences, deduplicating facts
        cleaned_statements: list[str] = []
        for m in cluster.memories:
            c = m.content.strip().rstrip(".")
            if c and c not in cleaned_statements:
                cleaned_statements.append(c)

        if len(cleaned_statements) == 1:
            synthesized = cleaned_statements[0]
        else:
            # Create abstracted synthesis
            synthesis_body = "; ".join(cleaned_statements)
            synthesized = f"Consolidated {cluster.topic} Profile: {synthesis_body}."

        synthesized_length = len(synthesized.split())
        compression_ratio = round(synthesized_length / max(total_orig_length, 1), 2)

        return SynthesizedClusterData(
            topic=cluster.topic,
            source_memory_ids=source_ids,
            synthesized_content=synthesized,
            confidence=avg_confidence,
            compression_ratio=compression_ratio,
            source_categories=source_categories,
        )
