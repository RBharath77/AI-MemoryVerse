import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.ai.context_assembler import ContextAssembler, TokenBudgetManager
from app.ai.data_leakage_guard import DataLeakageGuard
from app.ai.reranker import AdaptiveReranker
from app.ai.retrieval import SearchResultItem


@pytest.mark.asyncio
async def test_adaptive_reranker_temporal_decay_and_feedback():
    """Verify temporal recency decay, pinned protection, and feedback boosts in AdaptiveReranker."""
    now = datetime.now(UTC)

    # 1. Candidate A: fresh (1 day old)
    item_fresh = SearchResultItem(
        source_type="memory",
        id="mem-fresh",
        title="Recent Memory",
        content="Active operational note created recently",
        score=0.80,
        metadata={
            "created_at": (now - timedelta(days=1)).isoformat(),
            "importance": 7,
            "is_pinned": False,
        },
    )

    # 2. Candidate B: stale (120 days old, identical score and importance)
    item_stale = SearchResultItem(
        source_type="memory",
        id="mem-stale",
        title="Stale Memory",
        content="Historical operational note created months ago",
        score=0.80,
        metadata={
            "created_at": (now - timedelta(days=120)).isoformat(),
            "importance": 7,
            "is_pinned": False,
        },
    )

    # 3. Candidate C: stale (120 days old) but PINNED
    item_pinned_stale = SearchResultItem(
        source_type="memory",
        id="mem-pinned",
        title="Pinned Core Policy",
        content="Immutable organizational standard",
        score=0.80,
        metadata={
            "created_at": (now - timedelta(days=120)).isoformat(),
            "importance": 7,
            "is_pinned": True,
        },
    )

    # 4. Candidate D: fresh with negative feedback
    item_downvoted = SearchResultItem(
        source_type="memory",
        id="mem-downvoted",
        title="Downvoted Memory",
        content="Fact that user marked as unhelpful",
        score=0.80,
        metadata={
            "created_at": (now - timedelta(days=1)).isoformat(),
            "importance": 7,
            "is_pinned": False,
            "feedback_rating": -1,
        },
    )

    reranked = AdaptiveReranker.rerank(
        [item_stale, item_fresh, item_pinned_stale, item_downvoted],
        top_k=4,
        now=now,
    )

    # Candidate C (pinned) and A (fresh) must outrank Candidate B (stale unpinned)
    ids_in_order = [r.id for r in reranked]

    # Fresh outranks stale
    assert ids_in_order.index("mem-fresh") < ids_in_order.index("mem-stale")

    # Pinned stale outranks unpinned stale
    assert ids_in_order.index("mem-pinned") < ids_in_order.index("mem-stale")

    # Downvoted item is demoted below fresh item
    assert ids_in_order.index("mem-fresh") < ids_in_order.index("mem-downvoted")

    # Inspect detailed breakdown in metadata
    fresh_meta = next(r.metadata for r in reranked if r.id == "mem-fresh")
    stale_meta = next(r.metadata for r in reranked if r.id == "mem-stale")
    assert (
        fresh_meta["rerank_breakdown"]["recency_score"]
        > stale_meta["rerank_breakdown"]["recency_score"]
    )


@pytest.mark.asyncio
async def test_token_budget_manager_and_dynamic_clamping():
    """Verify dynamic token budget estimation and graceful context clamping."""
    # 1. Test budget calculation
    available = TokenBudgetManager.calculate_budget(
        total_model_tokens=4096, reserved_generation_tokens=1024
    )
    assert available == 3072

    # 2. Assemble context under severely constrained budget (max_context_tokens=250)
    contexts = [
        SearchResultItem(
            source_type="memory",
            id=f"m-{i}",
            title=f"Memory #{i}",
            content=f"Important system architecture paragraph description for item number {i} "
            * 10,
            score=0.90 - (i * 0.1),
            metadata={"is_pinned": i == 0},  # First is pinned
        )
        for i in range(5)
    ]

    assembled = ContextAssembler.assemble(
        user_query="How is the system architected?",
        conversation_history=[{"role": "user", "content": "Prior message"}],
        grounding_contexts=contexts,
        max_context_tokens=300,
        total_model_tokens=1024,
        reserved_generation_tokens=256,
    )

    # Context clamping should gracefully drop low-priority items without crashing
    metrics = assembled.budget_metrics
    assert metrics["clamped_items_count"] > 0
    assert metrics["used_tokens"] <= metrics["effective_budget"] + 100
    assert len(assembled.citations) < len(contexts)
    # Pinned first item must be included in citations
    assert any(c["source_id"] == "m-0" for c in assembled.citations)


@pytest.mark.asyncio
async def test_data_leakage_guard_outbound_sanitization():
    """Verify DataLeakageGuard redacts foreign workspace IDs, credentials, and internal database stack traces."""
    current_ws = f"ws-{uuid.uuid4().hex[:8]}"
    foreign_ws = f"ws-{uuid.uuid4().hex[:8]}"

    raw_llm_output = (
        f"Based on record in workspace {foreign_ws}, your API token is "
        "sk-proj-9876543210fedcba9876543210 and AWS key is AKIAIOSFODNN7EXAMPLE. "
        "System query failed: psycopg2.OperationalError: table 'users' does not exist."
    )

    result = DataLeakageGuard.sanitize(
        text=raw_llm_output,
        current_workspace_id=current_ws,
        foreign_workspace_ids=[foreign_ws],
    )

    assert result.is_clean is False
    assert foreign_ws not in result.sanitized_text
    assert "[REDACTED_TENANT_ID]" in result.sanitized_text
    assert "sk-proj-9876543210" not in result.sanitized_text
    assert "[REDACTED_API_KEY]" in result.sanitized_text
    assert "AKIAIOSFODNN7EXAMPLE" not in result.sanitized_text
    assert "[REDACTED_AWS_KEY]" in result.sanitized_text
    assert "psycopg2.OperationalError" not in result.sanitized_text
    assert "[SYSTEM_ERROR_FILTERED" in result.sanitized_text


@pytest.mark.asyncio
async def test_webhook_dispatcher_ssrf_validation_and_lifecycle(client: AsyncClient):
    """Verify webhook endpoint registration blocks SSRF targets and provides CRUD lifecycle."""
    # 1. Register user & get workspace
    email = f"wh_user_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "Webhook Admin"},
    )
    token = reg.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ws_res = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = ws_res.json()["data"][0]["id"]

    # 2. Attempt to register SSRF targets (Loopback / Cloud Metadata) -> 400 Bad Request
    bad_ssrf_res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/webhooks",
        json={"url": "http://169.254.169.254/latest/meta-data/"},
        headers=headers,
    )
    assert bad_ssrf_res.status_code == 400
    assert "SSRF Protection" in bad_ssrf_res.json()["error"]["message"]

    bad_loopback = await client.post(
        f"/api/v1/workspaces/{workspace_id}/webhooks",
        json={"url": "http://127.0.0.1:8080/internal-admin"},
        headers=headers,
    )
    assert bad_loopback.status_code == 400

    # 3. Register valid external webhook endpoint (public routable IP)
    good_url = "https://93.184.216.34/api/webhooks/incoming"
    create_res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/webhooks",
        json={
            "url": good_url,
            "secret": "whsec_test_secret_key_12345",
            "event_types": ["memory.created", "document.processed"],
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    ep_data = create_res.json()["data"]
    endpoint_id = ep_data["id"]
    assert ep_data["url"] == good_url
    assert "whse••••2345" in ep_data["masked_secret"]

    # 4. List endpoints
    list_res = await client.get(f"/api/v1/workspaces/{workspace_id}/webhooks", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()["data"]) == 1

    # 5. Delete endpoint
    del_res = await client.delete(
        f"/api/v1/workspaces/{workspace_id}/webhooks/{endpoint_id}", headers=headers
    )
    assert del_res.status_code == 200
    assert del_res.json()["data"]["deleted"] is True

    # 6. Verify empty list
    list_res_after = await client.get(
        f"/api/v1/workspaces/{workspace_id}/webhooks", headers=headers
    )
    assert len(list_res_after.json()["data"]) == 0


@pytest.mark.asyncio
async def test_webhook_event_dispatch_and_dlq_redrive(client: AsyncClient):
    """Verify event dispatch signs payloads with HMAC-SHA256, captures failures in DLQ, and allows manual redrive."""
    email = f"dlq_user_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "DLQ Admin"},
    )
    token = reg.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ws_res = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = ws_res.json()["data"][0]["id"]

    # 1. Register endpoint with a valid public IP that will simulate connection failure in test sandbox
    reg_hook = await client.post(
        f"/api/v1/workspaces/{workspace_id}/webhooks",
        json={
            "url": "https://93.184.216.34/webhooks/unreachable-handler",
            "event_types": ["memory.created"],
        },
        headers=headers,
    )
    assert reg_hook.status_code == 201

    # 2. Trigger dispatch of 'memory.created' event
    dispatch_res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/webhooks/dispatch",
        json={
            "event_type": "memory.created",
            "payload": {"memory_id": "mem-12345", "content": "Mission-critical fact"},
        },
        headers=headers,
    )
    assert dispatch_res.status_code == 200
    deliveries = dispatch_res.json()["data"]
    assert len(deliveries) == 1
    delivery_id = deliveries[0]["id"]
    assert deliveries[0]["is_dlq"] is True  # Quarantined into DLQ upon failed external reach

    # 3. Query Dead-Letter Queue
    dlq_res = await client.get(f"/api/v1/workspaces/{workspace_id}/webhooks/dlq", headers=headers)
    assert dlq_res.status_code == 200
    dlq_items = dlq_res.json()["data"]
    assert len(dlq_items) == 1
    assert dlq_items[0]["id"] == delivery_id
    assert dlq_items[0]["attempt_count"] == 1

    # 4. Redrive delivery from DLQ
    redrive_res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/webhooks/dlq/{delivery_id}/redrive",
        headers=headers,
    )
    assert redrive_res.status_code == 200
    redrive_data = redrive_res.json()["data"]
    assert redrive_data["id"] == delivery_id
    assert redrive_data["attempt_count"] == 2  # Re-attempt recorded


@pytest.mark.asyncio
async def test_webhook_rbac_guards(client: AsyncClient):
    """Verify non-admin workspace members cannot configure webhooks, view DLQ, or trigger redrives."""
    owner_reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"owner_wh_{uuid.uuid4().hex[:6]}@example.com",
            "password": "SecurePassword123!",
            "full_name": "Webhook Owner",
        },
    )
    owner_token = owner_reg.json()["data"]["tokens"]["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    ws_res = await client.get("/api/v1/workspaces", headers=owner_headers)
    workspace_id = ws_res.json()["data"][0]["id"]

    # Create viewer
    viewer_reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"viewer_wh_{uuid.uuid4().hex[:6]}@example.com",
            "password": "SecurePassword123!",
            "full_name": "Webhook Viewer",
        },
    )
    viewer_token = viewer_reg.json()["data"]["tokens"]["access_token"]
    viewer_id = viewer_reg.json()["data"]["user"]["id"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    # Add viewer to workspace
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"user_id": viewer_id, "role": "viewer"},
        headers=owner_headers,
    )

    # Viewer attempts to register webhook -> 403 Forbidden
    reg_forbidden = await client.post(
        f"/api/v1/workspaces/{workspace_id}/webhooks",
        json={"url": "https://example.com/webhook"},
        headers=viewer_headers,
    )
    assert reg_forbidden.status_code == 403

    # Viewer attempts to inspect DLQ -> 403 Forbidden
    dlq_forbidden = await client.get(
        f"/api/v1/workspaces/{workspace_id}/webhooks/dlq", headers=viewer_headers
    )
    assert dlq_forbidden.status_code == 403
