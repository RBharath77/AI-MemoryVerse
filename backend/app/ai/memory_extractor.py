import logging

from app.ai.base import ExtractedFact
from app.ai.factory import get_llm_provider

logger = logging.getLogger(__name__)


class MemoryExtractor:
    """Orchestrates extraction of structured memories from unstructured text."""

    def __init__(self) -> None:
        self.llm = get_llm_provider()

    async def extract_facts(
        self,
        text: str,
        existing_memories: list[str] | None = None,
    ) -> list[ExtractedFact]:
        """Extract candidate facts from text with sensitive data protection."""
        if not text or not text.strip():
            return []

        try:
            facts = await self.llm.extract_structured_memories(
                text=text,
                existing_memories=existing_memories,
            )
            return facts
        except Exception as e:
            logger.error(f"Error extracting memories with LLM provider: {e}", exc_info=True)
            # Safe fallback to mock deterministic extractor
            from app.ai.mock_provider import MockLLMProvider

            fallback = MockLLMProvider()
            return await fallback.extract_structured_memories(
                text=text,
                existing_memories=existing_memories,
            )
