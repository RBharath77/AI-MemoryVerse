import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.database import async_session_factory
from app.models.memory import Memory
from app.services.memory_service import MemoryService


@pytest.mark.asyncio
async def test_system_telemetry_diagnostics_endpoint(client: AsyncClient):
    """Verify system telemetry health check endpoint returns nominal status and latency metrics."""
    res = await client.get("/api/v1/health/system")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "nominal"
    assert data["database"]["status"] == "connected"
    assert isinstance(data["database"]["latency_ms"], float)
    assert data["database"]["latency_ms"] >= 0.0
    assert "active_cached_queries" in data["semantic_cache"]
    assert data["ai_engine"]["embedding_dimensions"] == 1536


@pytest.mark.asyncio
async def test_ebbinghaus_retention_strength_and_decay_analytics(client: AsyncClient):
    """Verify biological forgetting curve decay calculation and workspace decay analytics."""
    # 1. Register user & get workspace
    email = f"ebbinghaus_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "Decay Tester"},
    )
    token = reg.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ws_res = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = ws_res.json()["data"][0]["id"]
    ws_headers = {**headers, "X-Workspace-ID": workspace_id}

    # 2. Create pinned memory (should never decay)
    m_pinned = await client.post(
        "/api/v1/memories",
        json={
            "content": "Pinned corporate tenet never forgotten",
            "category": "semantic",
            "is_pinned": True,
        },
        headers=ws_headers,
    )
    assert m_pinned.status_code == 201

    # 3. Create fresh memory (recent, strong retention)
    m_fresh = await client.post(
        "/api/v1/memories",
        json={"content": "Fresh deployment observation", "category": "episodic"},
        headers=ws_headers,
    )
    assert m_fresh.status_code == 201

    # 4. Create aging memory and simulate 90 days elapsed since last access
    m_aging = await client.post(
        "/api/v1/memories",
        json={"content": "Infrequently accessed legacy decision", "category": "project"},
        headers=ws_headers,
    )
    assert m_aging.status_code == 201
    m_aging_id = m_aging.json()["data"]["id"]

    # Manually backdate aging memory in DB
    past_date = (datetime.now(UTC) - timedelta(days=90)).isoformat()
    async with async_session_factory() as db:
        mem = await db.get(Memory, m_aging_id)
        assert mem is not None
        meta = dict(mem.extra_metadata or {})
        meta["last_accessed_at"] = past_date
        mem.extra_metadata = meta
        await db.commit()

    # 5. Fetch decay analytics
    decay_res = await client.get("/api/v1/memories/decay-analytics", headers=ws_headers)
    assert decay_res.status_code == 200
    analytics = decay_res.json()["data"]
    assert analytics["total_memories"] >= 3
    assert analytics["strong_count"] >= 2  # Pinned and Fresh
    assert analytics["fading_count"] + analytics["dormant_count"] >= 1  # Aging memory decayed
    assert analytics["average_retention"] > 0.0


@pytest.mark.asyncio
async def test_memory_active_reinforcement(client: AsyncClient):
    """Verify active reinforcement boosts memory stability and resets elapsed decay window."""
    email = f"reinforce_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "Reinforce User"},
    )
    token = reg.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ws_res = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = ws_res.json()["data"][0]["id"]
    ws_headers = {**headers, "X-Workspace-ID": workspace_id}

    # 1. Create memory
    mem_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "Important algorithm details requiring periodic reinforcement",
            "category": "semantic",
        },
        headers=ws_headers,
    )
    assert mem_res.status_code == 201
    mem_id = mem_res.json()["data"]["id"]

    # 2. Backdate memory by 60 days
    past_date = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    async with async_session_factory() as db:
        mem = await db.get(Memory, mem_id)
        assert mem is not None
        meta = dict(mem.extra_metadata or {})
        meta["last_accessed_at"] = past_date
        mem.extra_metadata = meta
        await db.commit()

        # Check decayed strength
        strength_before, _, _ = MemoryService.compute_retention_strength(mem)
        assert strength_before < 0.70  # Decayed significantly

    # 3. Trigger active reinforcement
    reinf_res = await client.post(
        f"/api/v1/memories/{mem_id}/reinforce",
        headers=ws_headers,
    )
    assert reinf_res.status_code == 200
    reinf_data = reinf_res.json()["data"]
    assert reinf_data["id"] == mem_id
    assert reinf_data["retention_strength"] >= 0.99  # Reset back to near 1.0
    assert reinf_data["stability_days"] > 30.0  # Stability factor increased
    assert reinf_data["access_count"] >= 3  # Initial + reinforced


@pytest.mark.asyncio
async def test_cryptographic_tamper_evident_integrity_verification(client: AsyncClient):
    """Verify row-level HMAC-SHA256 signatures detect out-of-band database tampering."""
    email = f"integrity_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "Audit User"},
    )
    token = reg.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ws_res = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = ws_res.json()["data"][0]["id"]
    ws_headers = {**headers, "X-Workspace-ID": workspace_id}

    # 1. Create genuine memory through official API
    mem_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "Original untampered memory content",
            "category": "semantic",
            "importance": 8,
        },
        headers=ws_headers,
    )
    assert mem_res.status_code == 201
    mem_id = mem_res.json()["data"]["id"]

    # 2. Run integrity verification -> must report secure
    audit_clean = await client.post("/api/v1/memories/integrity/verify", headers=ws_headers)
    assert audit_clean.status_code == 200
    clean_data = audit_clean.json()["data"]
    assert clean_data["is_compromised"] is False
    assert clean_data["valid_count"] >= 1
    assert clean_data["tampered_count"] == 0

    # 3. Simulate malicious direct SQL tampering of memory row without valid application signature
    async with async_session_factory() as db:
        await db.execute(
            text(
                "UPDATE memories SET content = 'MALICIOUS_TAMPERED_INJECTION_TEXT' WHERE id = :id"
            ),
            {"id": mem_id},
        )
        await db.commit()

    # 4. Re-run integrity verification -> must detect tampered record!
    audit_tampered = await client.post("/api/v1/memories/integrity/verify", headers=ws_headers)
    assert audit_tampered.status_code == 200
    tampered_data = audit_tampered.json()["data"]
    assert tampered_data["is_compromised"] is True
    assert tampered_data["tampered_count"] >= 1
    assert mem_id in tampered_data["tampered_ids"]
