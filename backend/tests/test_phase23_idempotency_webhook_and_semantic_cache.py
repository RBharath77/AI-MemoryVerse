import json
import time
import uuid

import pytest
from httpx import AsyncClient

from app.ai.semantic_cache import SemanticCache
from app.core.idempotency import IdempotencyService
from app.core.webhook import WebhookSignatureService


@pytest.fixture(autouse=True)
def clean_idempotency_and_cache():
    IdempotencyService.clear()
    SemanticCache.clear()
    yield
    IdempotencyService.clear()
    SemanticCache.clear()


@pytest.mark.asyncio
async def test_memory_creation_idempotency_replay_protection(client: AsyncClient):
    """Verify Idempotency-Key prevents duplicate memory creation on retried requests."""
    # 1. Register test user
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "idempotent_user@example.com",
            "password": "SecurePassword123!",
            "full_name": "Idempotent User",
        },
    )
    assert reg.status_code == 201
    token = reg.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    idempotency_key = f"idem-mem-{uuid.uuid4().hex}"
    req_headers = {**headers, "Idempotency-Key": idempotency_key}

    payload = {
        "content": "Mission-critical system memory fact requiring zero duplicates.",
        "category": "semantic",
        "importance": 8,
    }

    # 2. First call: Cache miss, creates new memory
    res1 = await client.post("/api/v1/memories", json=payload, headers=req_headers)
    assert res1.status_code == 201
    assert res1.headers.get("X-Cache-Lookup") == "MISS-IDEMPOTENT"
    mem1_id = res1.json()["data"]["id"]

    # 3. Second call: Cache hit, returns cached response without duplicate database insertion
    res2 = await client.post("/api/v1/memories", json=payload, headers=req_headers)
    assert res2.status_code == 201
    assert res2.headers.get("X-Cache-Lookup") == "HIT-IDEMPOTENT"
    assert res2.json()["data"]["id"] == mem1_id

    # 4. Verify exactly 1 memory exists in the workspace
    list_res = await client.get("/api/v1/memories", headers=headers)
    assert list_res.status_code == 200
    assert list_res.json()["data"]["total"] == 1


@pytest.mark.asyncio
async def test_idempotency_invalid_key_length(client: AsyncClient):
    """Verify Idempotency-Key header validates minimum and maximum length bounds."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "idempotent_bounds@example.com",
            "password": "SecurePassword123!",
            "full_name": "Bounds User",
        },
    )
    headers = {"Authorization": f"Bearer {reg.json()['data']['tokens']['access_token']}"}

    # Too short (< 8 chars)
    short_res = await client.post(
        "/api/v1/memories",
        json={"content": "Test content", "category": "semantic"},
        headers={**headers, "Idempotency-Key": "short"},
    )
    assert short_res.status_code == 400
    assert "8 and 128 characters" in short_res.json()["error"]["message"]

    # Too long (> 128 chars)
    long_res = await client.post(
        "/api/v1/memories",
        json={"content": "Test content", "category": "semantic"},
        headers={**headers, "Idempotency-Key": "a" * 130},
    )
    assert long_res.status_code == 400
    assert "8 and 128 characters" in long_res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_chat_message_idempotency(client: AsyncClient):
    """Verify sending conversation messages with Idempotency-Key prevents double generation."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "chat_idempotency@example.com",
            "password": "SecurePassword123!",
            "full_name": "Chat Idempotent",
        },
    )
    token = reg.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create conversation
    conv_res = await client.post(
        "/api/v1/chat/conversations",
        json={"title": "Idempotent Chat"},
        headers=headers,
    )
    conv_id = conv_res.json()["data"]["id"]

    idempotency_key = f"idem-chat-{uuid.uuid4().hex}"
    chat_headers = {**headers, "Idempotency-Key": idempotency_key}

    msg_payload = {"content": "What is AI-MemoryVerse?", "stream": False}

    # 1. First send: executes generation
    res1 = await client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        json=msg_payload,
        headers=chat_headers,
    )
    assert res1.status_code == 200
    assert res1.headers.get("X-Cache-Lookup") == "MISS-IDEMPOTENT"
    reply_1 = res1.json()["data"]["content"]

    # 2. Second send with identical key: returns cached assistant response
    res2 = await client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        json=msg_payload,
        headers=chat_headers,
    )
    assert res2.status_code == 200
    assert res2.headers.get("X-Cache-Lookup") == "HIT-IDEMPOTENT"
    assert res2.json()["data"]["content"] == reply_1


@pytest.mark.asyncio
async def test_webhook_hmac_signature_generation_and_verification():
    """Verify HMAC-SHA256 signature calculation, constant-time validation, and anti-replay protection."""
    secret = "whsec_super_secret_webhook_signing_key_123"
    payload = {"event": "memory.created", "memory_id": "mem-123", "importance": 9}
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")

    # 1. Generate signature
    sig_header, ts = WebhookSignatureService.sign_payload(payload_bytes, secret)
    assert sig_header.startswith(f"t={ts},v1=")

    # 2. Verify signature
    assert WebhookSignatureService.verify_signature(payload_bytes, sig_header, secret) is True

    # 3. Tampered payload fails verification
    tampered_bytes = json.dumps({"event": "memory.created", "memory_id": "mem-TAMPERED"}).encode(
        "utf-8"
    )
    assert WebhookSignatureService.verify_signature(tampered_bytes, sig_header, secret) is False

    # 4. Incorrect secret fails verification
    assert (
        WebhookSignatureService.verify_signature(payload_bytes, sig_header, "wrong_secret") is False
    )

    # 5. Expired timestamp outside tolerance window fails verification (Anti-Replay)
    old_ts = int(time.time()) - 400  # 400 seconds ago > 300s tolerance
    old_sig_header, _ = WebhookSignatureService.sign_payload(
        payload_bytes, secret, timestamp=old_ts
    )
    assert (
        WebhookSignatureService.verify_signature(
            payload_bytes, old_sig_header, secret, tolerance_seconds=300
        )
        is False
    )


@pytest.mark.asyncio
async def test_agent_webhook_verification_endpoint(client: AsyncClient):
    """Verify outgoing webhook signature verification endpoint."""
    secret = "endpoint_webhook_test_secret"
    payload = {"task_id": "task-001", "action": "notify_partner"}
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")

    sig_header, _ = WebhookSignatureService.sign_payload(payload_bytes, secret)

    # Verify via endpoint
    verify_res = await client.post(
        "/api/v1/agents/webhooks/verify",
        json={
            "payload": payload,
            "signature_header": sig_header,
            "secret": secret,
            "tolerance_seconds": 300,
        },
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["data"]["valid"] is True


@pytest.mark.asyncio
async def test_multi_tenant_rag_semantic_caching_and_invalidation(client: AsyncClient):
    """Verify semantic RAG caching saves redundant generation, enforces tenant isolation, and invalidates on write."""
    # 1. Register User A (Workspace A)
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "cache_a@example.com",
            "password": "SecurePassword123!",
            "full_name": "User A",
        },
    )
    headers_a = {"Authorization": f"Bearer {reg_a.json()['data']['tokens']['access_token']}"}

    # 2. Register User B (Workspace B)
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "cache_b@example.com",
            "password": "SecurePassword123!",
            "full_name": "User B",
        },
    )
    headers_b = {"Authorization": f"Bearer {reg_b.json()['data']['tokens']['access_token']}"}

    # Create conversations
    conv_a = (
        await client.post("/api/v1/chat/conversations", json={"title": "Chat A"}, headers=headers_a)
    ).json()["data"]["id"]
    conv_b = (
        await client.post("/api/v1/chat/conversations", json={"title": "Chat B"}, headers=headers_b)
    ).json()["data"]["id"]

    query = "What is the primary mission of AI-MemoryVerse?"

    # 3. User A queries: Cache MISS -> executes LLM and populates cache
    res1_a = await client.post(
        f"/api/v1/chat/conversations/{conv_a}/messages",
        json={"content": query, "stream": False},
        headers=headers_a,
    )
    assert res1_a.status_code == 200
    first_ans_a = res1_a.json()["data"]["content"]

    # 4. User A queries again in a new conversation with normalized whitespace/case: Cache HIT!
    conv_a2 = (
        await client.post(
            "/api/v1/chat/conversations", json={"title": "Chat A2"}, headers=headers_a
        )
    ).json()["data"]["id"]
    res2_a = await client.post(
        f"/api/v1/chat/conversations/{conv_a2}/messages",
        json={"content": "what is the primary mission of ai-memoryverse?", "stream": False},
        headers=headers_a,
    )
    assert res2_a.status_code == 200
    assert res2_a.json()["data"]["content"] == first_ans_a
    assert res2_a.json()["data"]["extra_metadata"].get("cached") is True

    # 5. User B queries identical question in Workspace B: must NOT leak Workspace A's cache!
    res_b = await client.post(
        f"/api/v1/chat/conversations/{conv_b}/messages",
        json={"content": query, "stream": False},
        headers=headers_b,
    )
    assert res_b.status_code == 200
    # Extra metadata in Workspace B should NOT have cached == True from Workspace A
    assert res_b.json()["data"]["extra_metadata"].get("cached") is not True

    # 6. User A creates a new memory in Workspace A -> triggers cache invalidation!
    mem_res = await client.post(
        "/api/v1/memories",
        json={"content": "New critical company update.", "category": "semantic"},
        headers=headers_a,
    )
    assert mem_res.status_code == 201

    # 7. User A queries again in Workspace A: cache was invalidated, so it runs fresh RAG!
    conv_a3 = (
        await client.post(
            "/api/v1/chat/conversations", json={"title": "Chat A3"}, headers=headers_a
        )
    ).json()["data"]["id"]
    res3_a = await client.post(
        f"/api/v1/chat/conversations/{conv_a3}/messages",
        json={"content": query, "stream": False},
        headers=headers_a,
    )
    assert res3_a.status_code == 200
    assert res3_a.json()["data"]["extra_metadata"].get("cached") is not True
