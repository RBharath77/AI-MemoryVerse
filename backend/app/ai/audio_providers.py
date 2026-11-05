import io
import math
import struct
import wave
from typing import Any

from app.ai.base import (
    BaseSTTProvider,
    BaseTTSProvider,
    STTResponse,
    TTSResponse,
)
from app.core.config import settings


def _generate_synthetic_wav(duration_seconds: float = 0.5, freq: float = 440.0) -> bytes:
    """Generate a valid PCM 16-bit mono 16000Hz WAV byte stream for offline/mock playback."""
    sample_rate = 16000
    num_samples = int(sample_rate * duration_seconds)
    buffer = io.BytesIO()

    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        # Generate smooth sine wave
        samples = []
        for i in range(num_samples):
            t = float(i) / sample_rate
            # 440Hz tone with slight fade-out
            amplitude = 16000 * (1.0 - (float(i) / num_samples))
            val = int(amplitude * math.sin(2.0 * math.pi * freq * t))
            samples.append(struct.pack("<h", val))

        wav_file.writeframes(b"".join(samples))

    return buffer.getvalue()


class MockSTTProvider(BaseSTTProvider):
    """Deterministic Speech-to-Text provider for test & offline environments."""

    def __init__(self, default_transcript: str | None = None):
        self.default_transcript = default_transcript

    async def transcribe_audio(
        self,
        audio_data: bytes,
        filename: str = "audio.wav",
        content_type: str = "audio/wav",
    ) -> STTResponse:
        if not audio_data:
            return STTResponse(text="", duration=0.0, confidence=0.0)

        # If a specific transcript is preset, use it
        if self.default_transcript:
            return STTResponse(
                text=self.default_transcript,
                duration=2.5,
                confidence=0.98,
            )

        # Check if the audio filename or header hints at something
        if "test_query" in filename.lower():
            text = "Tell me about our Next.js and FastAPI architecture."
        else:
            text = "What are the key memories and project updates in my workspace?"

        return STTResponse(
            text=text,
            language="en",
            duration=len(audio_data) / 32000.0,
            confidence=0.95,
        )


class MockTTSProvider(BaseTTSProvider):
    """Deterministic Text-to-Speech provider returning valid audio bytes."""

    async def synthesize_speech(
        self,
        text: str,
        voice: str = "alloy",
    ) -> TTSResponse:
        clean_text = text.strip() if text else "Silence."
        # Approximate duration: ~150 words per minute
        word_count = len(clean_text.split())
        est_duration = max(0.5, (word_count / 150.0) * 60.0)
        # Cap synthetic duration at 1.5s for fast test byte generation
        wav_bytes = _generate_synthetic_wav(duration_seconds=min(1.5, est_duration))

        return TTSResponse(
            audio_bytes=wav_bytes,
            content_type="audio/wav",
            duration_estimate=est_duration,
        )


class OpenAISTTProvider(BaseSTTProvider):
    """OpenAI Whisper Speech-to-Text provider."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        try:
            from openai import AsyncOpenAI

            self.client: Any = AsyncOpenAI(api_key=api_key)
        except ImportError:
            self.client = None

    async def transcribe_audio(
        self,
        audio_data: bytes,
        filename: str = "audio.wav",
        content_type: str = "audio/wav",
    ) -> STTResponse:
        if not self.client:
            mock = MockSTTProvider()
            return await mock.transcribe_audio(audio_data, filename, content_type)

        audio_file = (filename, audio_data, content_type)
        transcript = await self.client.audio.transcriptions.create(
            model=settings.OPENAI_WHISPER_MODEL or "whisper-1",
            file=audio_file,
        )
        return STTResponse(
            text=transcript.text.strip(),
            language="en",
            confidence=0.98,
        )


class OpenAITTSProvider(BaseTTSProvider):
    """OpenAI TTS Speech generation provider."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        try:
            from openai import AsyncOpenAI

            self.client: Any = AsyncOpenAI(api_key=api_key)
        except ImportError:
            self.client = None

    async def synthesize_speech(
        self,
        text: str,
        voice: str = "alloy",
    ) -> TTSResponse:
        if not self.client:
            mock = MockTTSProvider()
            return await mock.synthesize_speech(text, voice)

        response = await self.client.audio.speech.create(
            model=settings.OPENAI_TTS_MODEL or "tts-1",
            voice=voice,
            input=text,
        )
        audio_bytes = response.content
        return TTSResponse(
            audio_bytes=audio_bytes,
            content_type="audio/mpeg",
            duration_estimate=max(1.0, len(text.split()) / 2.5),
        )
