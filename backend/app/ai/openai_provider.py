import json
import logging
from typing import Any

import httpx

from app.ai.base import (
    BaseEmbeddingProvider,
    BaseLLMProvider,
    ExtractedFact,
    LLMMessage,
    LLMResponse,
)

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider, BaseEmbeddingProvider):
    """OpenAI API Provider implementation using httpx for async execution."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        embedding_model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.embedding_model = embedding_model
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if "openrouter.ai" in self.base_url:
            headers["HTTP-Referer"] = "https://memoryverse.ai"
            headers["X-Title"] = "AI-MemoryVerse"
        return headers

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", self.model),
            usage=data.get("usage", {}),
            finish_reason=choice.get("finish_reason", "stop"),
            raw_response=data,
        )

    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> LLMResponse:
        formatted = [{"role": m.role, "content": m.content} for m in messages]
        payload = {
            "model": self.model,
            "messages": formatted,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", self.model),
            usage=data.get("usage", {}),
            finish_reason=choice.get("finish_reason", "stop"),
            raw_response=data,
        )

    async def extract_structured_memories(
        self,
        text: str,
        existing_memories: list[str] | None = None,
    ) -> list[ExtractedFact]:
        system_prompt = (
            "You are an AI Memory Extraction Engine. Extract atomic personal/project facts. "
            "Categories must be one of: 'episodic', 'semantic', 'project', 'preference'. "
            "Output JSON object with a single 'facts' array containing items: "
            "{'content': str, 'category': str, 'importance': int (1-10), "
            "'confidence': float (0.0-1.0), 'tags': list[str]}. "
            "Do NOT include passwords, private secrets, or credit cards."
        )

        user_prompt = f"Extract facts from the following text:\n---\n{text}\n---"
        if existing_memories:
            user_prompt += "\nExisting context:\n" + "\n".join(
                f"- {m}" for m in existing_memories[:10]
            )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
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

    async def get_embedding(self, text: str) -> list[float]:
        payload = {
            "model": self.embedding_model,
            "input": text,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        return data["data"][0]["embedding"]

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        payload = {
            "model": self.embedding_model,
            "input": texts,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        return [item["embedding"] for item in data["data"]]
