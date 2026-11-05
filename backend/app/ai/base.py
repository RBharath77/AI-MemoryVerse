from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMMessage:
    role: str  # "system", "user", "assistant"
    content: str
    name: str | None = None


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    raw_response: Any = None


@dataclass
class ExtractedFact:
    content: str
    category: str  # "episodic", "semantic", "project", "preference"
    importance: int  # 1 - 10
    confidence: float  # 0.0 - 1.0
    tags: list[str] = field(default_factory=list)
    valid_from: str | None = None
    valid_until: str | None = None
    is_sensitive: bool = False
    source_context: str | None = None


class BaseLLMProvider(ABC):
    """Abstract interface for LLM providers (OpenAI, Gemini, Anthropic, Mock)."""

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate text completion from a prompt."""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate response from a chat conversation."""
        pass

    @abstractmethod
    async def extract_structured_memories(
        self,
        text: str,
        existing_memories: list[str] | None = None,
    ) -> list[ExtractedFact]:
        """Extract atomic memory facts from unstructured text."""
        pass


class BaseEmbeddingProvider(ABC):
    """Abstract interface for vector embedding providers."""

    @abstractmethod
    async def get_embedding(self, text: str) -> list[float]:
        """Generate vector embedding for a single text."""
        pass

    @abstractmethod
    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a list of texts."""
        pass


@dataclass
class STTResponse:
    text: str
    language: str = "en"
    duration: float = 0.0
    confidence: float = 1.0


@dataclass
class TTSResponse:
    audio_bytes: bytes
    content_type: str = "audio/wav"
    duration_estimate: float = 0.0


class BaseSTTProvider(ABC):
    """Abstract interface for Speech-to-Text providers."""

    @abstractmethod
    async def transcribe_audio(
        self,
        audio_data: bytes,
        filename: str = "audio.wav",
        content_type: str = "audio/wav",
    ) -> STTResponse:
        """Transcribe recorded speech into text."""
        pass


class BaseTTSProvider(ABC):
    """Abstract interface for Text-to-Speech providers."""

    @abstractmethod
    async def synthesize_speech(
        self,
        text: str,
        voice: str = "alloy",
    ) -> TTSResponse:
        """Synthesize spoken audio from text."""
        pass
