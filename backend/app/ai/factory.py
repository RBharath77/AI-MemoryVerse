import logging

from app.ai.base import BaseEmbeddingProvider, BaseLLMProvider
from app.ai.gemini_provider import GeminiProvider
from app.ai.mock_provider import MockEmbeddingProvider, MockLLMProvider
from app.ai.openai_provider import OpenAIProvider
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_llm_provider() -> BaseLLMProvider:
    """Return configured LLM provider instance, safely defaulting to mock if credentials missing."""
    provider_type = (settings.LLM_PROVIDER or "mock").lower()

    if provider_type == "openai":
        if settings.LLM_API_KEY:
            return OpenAIProvider(
                api_key=settings.LLM_API_KEY,
                model=settings.LLM_MODEL or "gpt-4o-mini",
            )
        logger.warning("OpenAI API key missing. Falling back to MockLLMProvider.")
        return MockLLMProvider()

    if provider_type == "gemini":
        if settings.LLM_API_KEY:
            return GeminiProvider(
                api_key=settings.LLM_API_KEY,
                model=settings.LLM_MODEL or "gemini-1.5-flash",
            )
        logger.warning("Gemini API key missing. Falling back to MockLLMProvider.")
        return MockLLMProvider()

    return MockLLMProvider()


def get_embedding_provider() -> BaseEmbeddingProvider:
    """Return configured Embedding provider instance, safely defaulting to mock."""
    provider_type = (settings.EMBEDDING_PROVIDER or "mock").lower()

    if provider_type == "openai":
        if settings.EMBEDDING_API_KEY or settings.LLM_API_KEY:
            key = settings.EMBEDDING_API_KEY or settings.LLM_API_KEY
            return OpenAIProvider(
                api_key=key,
                embedding_model=settings.EMBEDDING_MODEL or "text-embedding-3-small",
            )
        logger.warning(
            "OpenAI API key for embeddings missing. Falling back to MockEmbeddingProvider."
        )
        return MockEmbeddingProvider(dimensions=settings.EMBEDDING_DIMENSIONS)

    return MockEmbeddingProvider(dimensions=settings.EMBEDDING_DIMENSIONS)
