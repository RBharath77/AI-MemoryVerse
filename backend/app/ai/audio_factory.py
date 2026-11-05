import logging

from app.ai.audio_providers import (
    BaseSTTProvider,
    BaseTTSProvider,
    MockSTTProvider,
    MockTTSProvider,
    OpenAISTTProvider,
    OpenAITTSProvider,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_stt_provider() -> BaseSTTProvider:
    """Return configured Speech-to-Text provider."""
    provider_name = (settings.SPEECH_PROVIDER or "mock").lower()

    if provider_name == "openai" and settings.LLM_API_KEY:
        return OpenAISTTProvider(api_key=settings.LLM_API_KEY)

    return MockSTTProvider()


def get_tts_provider() -> BaseTTSProvider:
    """Return configured Text-to-Speech provider."""
    provider_name = (settings.SPEECH_PROVIDER or "mock").lower()

    if provider_name == "openai" and settings.LLM_API_KEY:
        return OpenAITTSProvider(api_key=settings.LLM_API_KEY)

    return MockTTSProvider()

