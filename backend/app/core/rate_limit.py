import asyncio
import logging
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# Shared Redis client instance for distributed rate limiting
_redis_client = None


def get_rate_limit_redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis

            if getattr(settings, "REDIS_URL", None):
                _redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                )
            else:
                _redis_client = False
        except Exception as e:
            logger.debug(f"Redis unavailable for rate limiting: {e}")
            _redis_client = False
    return _redis_client if _redis_client is not False else None


class RateLimiter:
    """Sliding-window distributed & in-memory rate limiter dependency for FastAPI routes.

    Protects authentication, heavy search, and AI generation endpoints from
    brute-force attacks, credential stuffing, and volumetric flood.
    Uses Redis when available, with automatic graceful in-memory fallback.
    """

    def __init__(self, times: int = 10, seconds: int = 60) -> None:
        self.times = times
        self.seconds = seconds
        self._records: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    def _get_client_identifier(self, request: Request) -> str:
        # Check forwarded headers first if behind reverse proxy
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "127.0.0.1"

    async def __call__(self, request: Request) -> None:
        if not getattr(settings, "RATE_LIMIT_ENABLED", True):
            return

        client_id = self._get_client_identifier(request)
        now = time.time()
        window_start = now - self.seconds

        # 1. Attempt distributed Redis rate limiting if available
        r = get_rate_limit_redis()
        if r is not None:
            try:
                key = f"rate_limit:{client_id}:{self.times}:{self.seconds}"
                pipe = r.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, self.seconds + 5)
                results = await pipe.execute()
                count = results[2]
                if count > self.times:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Too many requests. Please slow down and try again later.",
                        headers={"Retry-After": str(self.seconds)},
                    )
                return
            except HTTPException:
                raise
            except Exception as e:
                logger.debug(f"Distributed rate limiting fallback to in-memory: {e}")

        # 2. Local in-memory sliding window fallback
        async with self._lock:
            queue = self._records[client_id]

            # Evict timestamps older than the sliding window
            while queue and queue[0] < window_start:
                queue.popleft()

            if len(queue) >= self.times:
                retry_after = int(self.seconds - (now - queue[0])) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please slow down and try again later.",
                    headers={"Retry-After": str(max(1, retry_after))},
                )

            queue.append(now)

    def reset(self) -> None:
        """Clear all in-memory tracking records (useful in tests)."""
        self._records.clear()
