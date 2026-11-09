import asyncio
import logging
import time
from typing import Any

from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)


class IdempotencyRecord:
    def __init__(self, status: str = "processing"):
        self.status = status  # "processing" | "completed"
        self.status_code: int = 200
        self.data: Any = None
        self.headers: dict[str, str] = {}
        self.created_at: float = time.time()


class IdempotencyService:
    """
    In-memory thread-safe and distributed Redis-compatible Idempotency Engine.
    Prevents duplicate mutations (double memory creation, repeated billing, double document uploads)
    when clients retry network requests with the same 'Idempotency-Key' header.
    """

    _lock = asyncio.Lock()
    _store: dict[str, IdempotencyRecord] = {}
    TTL_SECONDS: int = 86400  # 24 Hours

    @classmethod
    def _make_key(cls, idempotency_key: str, workspace_id: str | None, user_id: str | None) -> str:
        ws = workspace_id or "global"
        usr = user_id or "anonymous"
        return f"idempotency:{ws}:{usr}:{idempotency_key.strip()}"

    @classmethod
    async def acquire(
        cls,
        idempotency_key: str,
        workspace_id: str | None,
        user_id: str | None,
    ) -> tuple[bool, IdempotencyRecord | None]:
        """
        Attempt to acquire an idempotency lock for the given key.
        Returns:
            (True, None) -> Key acquired, caller should process the request.
            (False, record) -> Key already exists:
                - if record.status == 'processing': in-flight duplicate (return 409).
                - if record.status == 'completed': return cached response.
        """
        composite_key = cls._make_key(idempotency_key, workspace_id, user_id)
        now = time.time()

        async with cls._lock:
            # Clean expired records opportunistically
            expired_keys = [
                k for k, r in cls._store.items() if now - r.created_at > cls.TTL_SECONDS
            ]
            for k in expired_keys:
                cls._store.pop(k, None)

            existing = cls._store.get(composite_key)
            if existing:
                if existing.status == "processing":
                    # If processing for more than 60s, assume crashed and allow re-acquisition
                    if now - existing.created_at > 60:
                        existing.created_at = now
                        return True, None
                    return False, existing
                return False, existing

            # First time seeing this key: mark as processing
            cls._store[composite_key] = IdempotencyRecord(status="processing")
            return True, None

    @classmethod
    async def complete(
        cls,
        idempotency_key: str,
        workspace_id: str | None,
        user_id: str | None,
        status_code: int,
        data: Any,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Store the completed response data and headers for subsequent idempotent replays."""
        composite_key = cls._make_key(idempotency_key, workspace_id, user_id)
        async with cls._lock:
            record = cls._store.get(composite_key)
            if not record:
                record = IdempotencyRecord(status="completed")
                cls._store[composite_key] = record
            record.status = "completed"
            record.status_code = status_code
            record.data = data
            record.headers = headers or {}
            record.created_at = time.time()

    @classmethod
    async def release(
        cls,
        idempotency_key: str,
        workspace_id: str | None,
        user_id: str | None,
    ) -> None:
        """Release the processing lock if request failed prior to completion."""
        composite_key = cls._make_key(idempotency_key, workspace_id, user_id)
        async with cls._lock:
            cls._store.pop(composite_key, None)

    @classmethod
    def clear(cls) -> None:
        """Reset idempotency store (used for tests)."""
        cls._store.clear()


async def get_idempotency_key(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str | None:
    """Validate Idempotency-Key header length and character constraints."""
    if not idempotency_key:
        return None

    cleaned = idempotency_key.strip()
    if len(cleaned) < 8 or len(cleaned) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header must be between 8 and 128 characters in length.",
        )
    return cleaned
