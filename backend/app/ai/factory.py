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
    if provider_type == "mock":
        return MockLLMProvider()

    is_openrouter = provider_type == "openrouter" or (
        settings.LLM_API_KEY and settings.LLM_API_KEY.startswith("sk-or-v1-")
    )

    if provider_type == "openai" or is_openrouter:
        if settings.LLM_API_KEY:
            base_url = (
                settings.LLM_BASE_URL
                if settings.LLM_BASE_URL
                else (
                    "https://openrouter.ai/api/v1" if is_openrouter else "https://api.openai.com/v1"
                )
            )
            model = settings.LLM_MODEL or "gpt-4o-mini"
            if is_openrouter and not ("/" in model or ":" in model):
                model = f"openai/{model}"

            return OpenAIProvider(
                api_key=settings.LLM_API_KEY,
                model=model,
                base_url=base_url,
            )
        logger.warning("OpenAI / OpenRouter API key missing. Falling back to MockLLMProvider.")
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
    if provider_type == "mock":
        return MockEmbeddingProvider(dimensions=settings.EMBEDDING_DIMENSIONS)

    key = settings.EMBEDDING_API_KEY or settings.LLM_API_KEY
    is_openrouter = provider_type == "openrouter" or (key and key.startswith("sk-or-v1-"))

    if provider_type == "openai" or is_openrouter:
        if key:
            base_url = (
                settings.EMBEDDING_BASE_URL
                or settings.LLM_BASE_URL
                or (
                    "https://openrouter.ai/api/v1" if is_openrouter else "https://api.openai.com/v1"
                )
            )
            return OpenAIProvider(
                api_key=key,
                embedding_model=settings.EMBEDDING_MODEL or "text-embedding-3-small",
                base_url=base_url,
            )
        logger.warning(
            "OpenAI/OpenRouter embedding key missing. Falling back to MockEmbeddingProvider."
        )
        return MockEmbeddingProvider(dimensions=settings.EMBEDDING_DIMENSIONS)

    return MockEmbeddingProvider(dimensions=settings.EMBEDDING_DIMENSIONS)
