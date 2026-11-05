import json
import logging
from typing import Any

import httpx

from app.ai.base import (
    BaseLLMProvider,
    ExtractedFact,
    LLMMessage,
    LLMResponse,
)

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """Google Gemini API Provider implementation via REST API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-1.5-flash",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> LLMResponse:
        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        parts = []
        if system_prompt:
            parts.append({"text": f"System: {system_prompt}\n\nUser: {prompt}"})
        else:
            parts.append({"text": prompt})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates", [])
        text_content = ""
        if candidates and "content" in candidates[0]:
            parts_out = candidates[0]["content"].get("parts", [])
            if parts_out:
                text_content = parts_out[0].get("text", "")

        return LLMResponse(
            content=text_content,
            model=self.model,
            usage=data.get("usageMetadata", {}),
            raw_response=data,
        )

    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> LLMResponse:
        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        contents = []
        for m in messages:
            role = "user" if m.role in ("user", "system") else "model"
            contents.append({"role": role, "parts": [{"text": m.content}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates", [])
        text_content = ""
        if candidates and "content" in candidates[0]:
            parts_out = candidates[0]["content"].get("parts", [])
            if parts_out:
                text_content = parts_out[0].get("text", "")

        return LLMResponse(
            content=text_content,
            model=self.model,
            usage=data.get("usageMetadata", {}),
            raw_response=data,
        )

    async def extract_structured_memories(
        self,
        text: str,
        existing_memories: list[str] | None = None,
    ) -> list[ExtractedFact]:
        prompt = (
            "You are an AI Memory Extraction Engine. Extract atomic personal/project facts.\n"
            "Format the response strictly as a JSON object with a single 'facts' array of:\n"
            '{"content": string, "category": "episodic"|"semantic"|"project"|"preference", '
            '"importance": 1-10, "confidence": 0.0-1.0, "tags": [string]}.\n'
            "Do not include markdown tags or other text around the JSON.\n\n"
            f"Input text:\n{text}"
        )
        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates", [])
        text_content = "{}"
        if candidates and "content" in candidates[0]:
            parts_out = candidates[0]["content"].get("parts", [])
            if parts_out:
                text_content = parts_out[0].get("text", "{}")

        parsed = json.loads(text_content)
        raw_facts = parsed.get("facts", [])
        results: list[ExtractedFact] = []
        for rf in raw_facts:
            results.append(
                ExtractedFact(
                    content=rf.get("content", ""),
                    category=rf.get("category", "semantic"),
                    importance=int(rf.get("importance", 5)),
                    confidence=float(rf.get("confidence", 0.9)),
                    tags=rf.get("tags", []),
                )
            )
        return results
