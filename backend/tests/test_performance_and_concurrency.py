import asyncio
import time

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_concurrent_memory_creation(client: AsyncClient, auth_headers: dict):
    """Phase 6 Concurrency: Verify parallel insertion of memories without deadlocks or race conditions."""
    concurrency_count = 20

    async def _create_mem(i: int):
        payload = {
            "content": f"Concurrent memory fact #{i}: Distributed concurrency validation.",
            "category": "project",
            "importance": (i % 10) + 1,
        }
        res = await client.post("/api/v1/memories", json=payload, headers=auth_headers)
        assert res.status_code == 201
        return res.json()["data"]["id"]

    start_time = time.perf_counter()
    tasks = [_create_mem(i) for i in range(concurrency_count)]
    mem_ids = await asyncio.gather(*tasks)
    duration = time.perf_counter() - start_time

    assert len(set(mem_ids)) == concurrency_count, "All created memory IDs must be distinct"
    # Average time per request should demonstrate high async throughput
    assert duration < 5.0, f"Concurrent creation took {duration:.2f}s, expected < 5.0s"


@pytest.mark.asyncio
async def test_concurrent_hybrid_search_throughput(client: AsyncClient, auth_headers: dict):
    """Phase 6 Stress: Verify concurrent vector and lexical search queries under load."""
    # Seed memories for search
    await client.post(
        "/api/v1/memories",
        json={
            "content": "PostgreSQL pgvector provides HNSW vector similarity search.",
            "category": "project",
        },
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/memories",
        json={
            "content": "Antigravity powers advanced agentic workflows and automated coding.",
            "category": "semantic",
        },
        headers=auth_headers,
    )

    queries = [
        "PostgreSQL pgvector similarity",
        "Antigravity workflows agentic",
        "vector search performance",
        "concurrency throughput latency",
        "HNSW indexing database",
    ] * 4  # 20 concurrent queries

    async def _run_search(q: str):
        res = await client.post(
            "/api/v1/search/hybrid",
            json={"query": q, "top_k": 5},
            headers=auth_headers,
        )
        assert res.status_code == 200
        return res.json()["data"]["results"]

    start_time = time.perf_counter()
    tasks = [_run_search(q) for q in queries]
    results = await asyncio.gather(*tasks)
    duration = time.perf_counter() - start_time

    assert len(results) == len(queries)
    assert duration < 6.0, f"Concurrent search took {duration:.2f}s, expected < 6.0s"


@pytest.mark.asyncio
async def test_fuzzing_and_boundary_payloads(client: AsyncClient, auth_headers: dict):
    """Phase 6 Edge Cases: Test Unicode, XSS strings, special characters, and boundary inputs."""
    fuzz_payloads = [
        # Non-ASCII Multi-lingual scripts
        "🧠 🚀 💻 Testing Emoji & UTF-8 Multi-byte surrogate pairs",
        "こんにちは世界！これはAIメモリのテストです。",  # Japanese
        "مرحبا بكم في الذكاء الاصطناعي والذاكرة الدائمة",  # Arabic RTL
        "Привет, мир! Тестирование кириллических символов.",  # Russian
        # XSS / HTML injection payloads (must be stored safely without execution)
        "<script>alert('XSS-VULN')</script>",
        "<img src=x onerror=alert('IMG-XSS')>",
        "javascript:/*--></title></style></textarea></script></xmp><svg/onload='+/'/+/onmouseover=1/+/[*/[]/+alert(1)//'>",
        # SQL / JSON boundary strings
        '{"nested": {"injection": "\' OR 1=1 --", "null_byte": "\\u0000"}}',
        # Whitespace and punctuation
        "\t\n   \r\n\t Multi-line tab and carriage return test   \n\n",
    ]

    for payload in fuzz_payloads:
        res = await client.post(
            "/api/v1/memories",
            json={"content": payload, "category": "semantic", "importance": 5},
            headers=auth_headers,
        )
        assert res.status_code == 201, f"Failed on payload: {payload[:30]}"
        data = res.json()["data"]
        assert data["id"]
        assert data["content"] == payload


@pytest.mark.asyncio
async def test_rapid_token_refresh_lifecycle(client: AsyncClient):
    """Phase 6 Resiliency: Test session creation, token refresh, and stale token rejection."""
    reg_payload = {
        "email": "refresh_lifecycle@memoryverse.ai",
        "password": "Password123!",
        "full_name": "Lifecycle Tester",
        "workspace_name": "Lifecycle Workspace",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    refresh_token = reg_res.json()["data"]["tokens"]["refresh_token"]

    # First refresh succeeds
    ref1_res = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert ref1_res.status_code == 200
    new_refresh = ref1_res.json()["data"]["refresh_token"]
    assert new_refresh != refresh_token

    # Replay of old refresh token must be rejected (Token Reuse Detection)
    stale_res = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert stale_res.status_code == 401
