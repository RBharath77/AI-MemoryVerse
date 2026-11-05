import hashlib
import math
import re
from typing import Any

from app.ai.base import (
    BaseEmbeddingProvider,
    BaseLLMProvider,
    ExtractedFact,
    LLMMessage,
    LLMResponse,
)


class MockLLMProvider(BaseLLMProvider):
    """Deterministic Mock LLM Provider for local execution and automated testing."""

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> LLMResponse:
        return LLMResponse(
            content=f"Mock AI completion for: {prompt[:80]}...",
            model="mock-llm-v1",
            usage={
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": 15,
                "total_tokens": len(prompt.split()) + 15,
            },
        )

    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> LLMResponse:
        last_msg = messages[-1].content if messages else "Hello"
        return LLMResponse(
            content=f"Mock assistant response to: '{last_msg[:60]}'. How can I help you further?",
            model="mock-chat-v1",
            usage={
                "prompt_tokens": sum(len(m.content.split()) for m in messages),
                "completion_tokens": 20,
                "total_tokens": 50,
            },
        )

    async def extract_structured_memories(
        self,
        text: str,
        existing_memories: list[str] | None = None,
    ) -> list[ExtractedFact]:
        """Extract atomic facts from text using heuristic rule-based pattern matching."""
        facts: list[ExtractedFact] = []
        sentences = [s.strip() for s in re.split(r"[.\n;]+", text) if s.strip()]

        # Sensitive data regexes
        pwd_pattern = re.compile(
            r"\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|bearer[_-]?token)\b",
            re.IGNORECASE,
        )
        cc_pattern = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
        ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

        # Categorization patterns
        pref_pattern = re.compile(
            r"\b(prefer|love|like|hate|dislike|favorite|enjoy|always use|never use)\b",
            re.IGNORECASE,
        )
        proj_pattern = re.compile(
            r"\b(project|building|deploying|deadline|milestone|sprint|jira|repo|client|feature)\b",
            re.IGNORECASE,
        )
        epi_pattern = re.compile(
            r"\b(yesterday|today|tomorrow|last week|on monday|met with|had a meeting|scheduled)\b",
            re.IGNORECASE,
        )

        for sent in sentences:
            if len(sent) < 5:
                continue

            # Sensitive guardrail: Skip sentences leaking credentials or PII
            if pwd_pattern.search(sent) or cc_pattern.search(sent) or ssn_pattern.search(sent):
                continue

            # Categorize
            category = "semantic"
            importance = 5
            confidence = 0.90
            tags: list[str] = []

            if pref_pattern.search(sent):
                category = "preference"
                importance = 7
                tags.append("preference")
            elif proj_pattern.search(sent):
                category = "project"
                importance = 8
                tags.append("project")
            elif epi_pattern.search(sent):
                category = "episodic"
                importance = 6
                tags.append("event")
            else:
                tags.append("general")

            # Extract simple keyword tags
            words = [w.lower() for w in re.findall(r"\b[A-Za-z]{4,}\b", sent)]
            tags.extend(words[:3])

            facts.append(
                ExtractedFact(
                    content=sent,
                    category=category,
                    importance=importance,
                    confidence=confidence,
                    tags=list(set(tags)),
                    source_context=sent,
                )
            )

        return facts


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic Mock Embedding Provider returning normalized 1536-dim vectors."""

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    async def get_embedding(self, text: str) -> list[float]:
        # Hash text to generate repeatable pseudorandom float distribution
        h = hashlib.sha256(text.encode("utf-8")).digest()
        raw_vals = [float((h[i % len(h)] + i) % 100) / 100.0 - 0.5 for i in range(self.dimensions)]

        # Normalize to unit vector
        norm = math.sqrt(sum(x * x for x in raw_vals)) or 1.0
        return [x / norm for x in raw_vals]

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [await self.get_embedding(t) for t in texts]
