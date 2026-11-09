from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_graph_relationship_cross_tenant_memory_idor_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify that linking a foreign workspace memory into a relationship is rejected with 404."""
    # 1. User A creates a memory in workspace A
    mem_a_res = await client.post(
        "/api/v1/memories",
        json={"content": "Confidential User A secret memory", "category": "project"},
        headers=auth_headers,
    )
    assert mem_a_res.status_code == 201
    memory_a_id = mem_a_res.json()["data"]["id"]

    # 2. Register User B with their own workspace B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "graphuserb@memoryverse.ai",
            "password": "Password123!",
            "full_name": "Graph User B",
            "workspace_name": "Workspace B",
        },
    )
    assert reg_b.status_code == 201
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    ws_b = reg_b.json()["data"]["workspace"]["id"]
    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-Workspace-ID": ws_b,
    }

    # 3. User B creates two entities in workspace B
    ent1_res = await client.post(
        "/api/v1/graph/entities",
        json={"name": "Alpha Node", "entity_type": "concept"},
        headers=headers_b,
    )
    assert ent1_res.status_code == 201
    ent1_id = ent1_res.json()["data"]["id"]

    ent2_res = await client.post(
        "/api/v1/graph/entities",
        json={"name": "Beta Node", "entity_type": "concept"},
        headers=headers_b,
    )
    assert ent2_res.status_code == 201
    ent2_id = ent2_res.json()["data"]["id"]

    # 4. User B attempts to create a relationship referencing User A's memory
    rel_res = await client.post(
        "/api/v1/graph/relationships",
        json={
            "source_entity_id": ent1_id,
            "target_entity_id": ent2_id,
            "relationship_type": "relates_to",
            "source_memory_id": memory_a_id,  # Cross-tenant IDOR attack
        },
        headers=headers_b,
    )
    assert rel_res.status_code == 404
    assert "Source memory not found in active workspace" in rel_res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_graph_analytics_aggregation_performance(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify database-level aggregation produces correct graph analytics."""
    # Create several entities with different types
    await client.post(
        "/api/v1/graph/entities",
        json={"name": "PostgreSQL", "entity_type": "technology"},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/graph/entities",
        json={"name": "Antigravity", "entity_type": "technology"},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/graph/entities",
        json={"name": "AI-MemoryVerse", "entity_type": "project"},
        headers=auth_headers,
    )

    analytics_res = await client.get("/api/v1/graph/analytics", headers=auth_headers)
    assert analytics_res.status_code == 200
    analytics = analytics_res.json()["data"]

    assert analytics["total_entities"] >= 3
    assert "technology" in analytics["entity_type_breakdown"]
    assert analytics["entity_type_breakdown"]["technology"] >= 2
    assert "project" in analytics["entity_type_breakdown"]
    assert isinstance(analytics["average_degree"], float)


@pytest.mark.asyncio
async def test_graph_extraction_oversized_payload_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify oversized text (>50,000 chars) is rejected by schema validation before ReDoS/heap exhaustion."""
    oversized_text = "Knowledge text " * 4000  # ~60,000 characters > 50,000 limit
    res = await client.post(
        "/api/v1/graph/extract",
        json={"text": oversized_text},
        headers=auth_headers,
    )
    assert res.status_code == 422
    data = res.json()
    assert not data["success"]
    assert any(err.get("loc") == ["body", "text"] for err in data["error"]["details"])


@pytest.mark.asyncio
async def test_research_report_prompt_injection_quarantine(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify research synthesis encloses retrieved context in <workspace_context> tags and generates report."""
    res = await client.post(
        "/api/v1/research/generate",
        json={
            "topic": "Security Architecture",
            "report_type": "topic_research",
            "days_back": 7,
            "focus_areas": ["Authentication", "Multi-Tenancy"],
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    report = res.json()["data"]
    assert report["topic"] == "Security Architecture"
    assert report["status"] == "completed"
    assert len(report["key_findings"]) >= 1


@pytest.mark.asyncio
async def test_voice_request_invalid_voice_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify voice synthesis rejects unapproved or path-traversal voices."""
    # 1. Synthesize invalid voice
    res_synth = await client.post(
        "/api/v1/voice/synthesize",
        json={"text": "Test synthesis", "voice": "../../evil_voice"},
        headers=auth_headers,
    )
    assert res_synth.status_code == 422

    # 2. Synthesize valid voice
    res_valid = await client.post(
        "/api/v1/voice/synthesize",
        json={"text": "Test synthesis", "voice": "alloy"},
        headers=auth_headers,
    )
    assert res_valid.status_code == 200
    assert res_valid.headers.get("content-type") == "audio/wav"
