from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.ai.fact_differ import SemanticFactDiffer
from app.core import database as core_db
from app.models.memory import Memory, MemoryLink, MemoryStatus, MemoryVersion


@pytest.mark.asyncio
async def test_semantic_fact_differ_computation():
    """Verify SemanticFactDiffer correctly extracts additions, removals, and contradiction shifts."""
    # 1. Location contradiction
    old_text = "User lives in Seattle and works at Microsoft"
    new_text = "User moved to New York and works at Microsoft"
    diff = SemanticFactDiffer.compute_diff(old_text, new_text)

    assert "seattle" in diff.removed_tokens
    assert "york" in diff.added_tokens
    assert len(diff.contradicted_entities) == 1
    assert "Location" in diff.contradicted_entities[0]
    assert "seattle" in diff.contradicted_entities[0].lower()
    assert "york" in diff.contradicted_entities[0].lower()
    assert diff.similarity_score >= 0.35

    # 2. Theme contradiction
    diff_theme = SemanticFactDiffer.compute_diff(
        "Prefers dark mode theme in IDE",
        "Prefers light mode theme in IDE",
    )
    assert len(diff_theme.contradicted_entities) == 1
    assert "Theme" in diff_theme.contradicted_entities[0]

    # 3. Incremental fact addition
    diff_add = SemanticFactDiffer.compute_diff(
        "Senior backend engineer",
        "Senior backend engineer specialized in distributed systems and FastAPI",
    )
    assert len(diff_add.contradicted_entities) == 0
    assert "distributed" in diff_add.added_tokens
    assert "fastapi" in diff_add.added_tokens
    assert "Incremental fact addition" in diff_add.temporal_shift_summary


@pytest.mark.asyncio
async def test_memory_conflict_resolution_supersede(client: AsyncClient):
    """Verify candidate memory conflict resolution with supersede strategy."""
    # 1. Register User & Workspace
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "resolver@phase28.ai",
            "password": "Password123!",
            "full_name": "Conflict Resolver",
            "workspace_name": "Conflict WS",
        },
    )
    assert reg.status_code == 201
    token = reg.json()["data"]["tokens"]["access_token"]
    ws_id = reg.json()["data"]["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # 2. Ingest original memory
    mem1_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "User lives in Seattle Washington",
            "category": "semantic",
            "importance": 7,
        },
        headers=headers,
    )
    assert mem1_res.status_code == 201
    mem1_id = mem1_res.json()["data"]["id"]

    # 3. Ingest contradictory memory -> triggers conflict detection and PENDING_REVIEW
    mem2_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "User moved to London United Kingdom",
            "category": "semantic",
            "importance": 8,
        },
        headers=headers,
    )
    assert mem2_res.status_code == 201
    mem2_id = mem2_res.json()["data"]["id"]
    mem2_data = mem2_res.json()["data"]
    assert mem2_data["status"] == "pending_review"
    assert mem2_data["extra_metadata"]["conflict_detected"] is True

    # 4. Preview conflict diff endpoint
    diff_res = await client.get(
        f"/api/v1/memories/{mem2_id}/conflict-diff",
        headers=headers,
    )
    assert diff_res.status_code == 200
    diff_data = diff_res.json()["data"]
    assert "seattle" in diff_data["removed_tokens"]
    assert "london" in diff_data["added_tokens"]
    assert len(diff_data["contradicted_entities"]) >= 1

    # 5. Resolve conflict using 'supersede'
    resolve_res = await client.post(
        f"/api/v1/memories/{mem2_id}/resolve-conflict",
        json={"strategy": "supersede", "notes": "User relocated overseas in Q4."},
        headers=headers,
    )
    assert resolve_res.status_code == 200
    res_data = resolve_res.json()["data"]
    assert res_data["resolved_memory_id"] == mem2_id
    assert res_data["previous_memory_id"] == mem1_id
    assert res_data["strategy"] == "supersede"
    assert res_data["status"] == "approved"

    # 6. Verify database state
    async with core_db.async_session_factory() as db:
        m1 = (await db.execute(select(Memory).where(Memory.id == mem1_id))).scalar_one()
        m2 = (await db.execute(select(Memory).where(Memory.id == mem2_id))).scalar_one()
        assert m1.status == MemoryStatus.SUPERSEDED
        assert m1.superseded_by == m2.id
        assert m2.status == MemoryStatus.APPROVED

        # Verify MemoryLink was recorded
        link_q = select(MemoryLink).where(
            MemoryLink.source_memory_id == m2.id,
            MemoryLink.target_memory_id == m1.id,
            MemoryLink.relationship_type == "supersedes",
        )
        link = (await db.execute(link_q)).scalar_one_or_none()
        assert link is not None


@pytest.mark.asyncio
async def test_memory_conflict_resolution_merge_and_discard(client: AsyncClient):
    """Verify merge and discard conflict resolution strategies."""
    # 1. Register User & Workspace
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "merge_test@phase28.ai",
            "password": "Password123!",
            "full_name": "Merge Tester",
            "workspace_name": "Merge WS",
        },
    )
    token = reg.json()["data"]["tokens"]["access_token"]
    ws_id = reg.json()["data"]["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # 2. Ingest initial preference: prefers dark mode
    mem1_res = await client.post(
        "/api/v1/memories",
        json={"content": "Prefers dark mode theme in developer tools", "category": "preference"},
        headers=headers,
    )
    mem1_id = mem1_res.json()["data"]["id"]

    # 3. Ingest contradictory candidate: prefers light mode
    mem2_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "Prefers light mode theme during daylight hours",
            "category": "preference",
        },
        headers=headers,
    )
    mem2_id = mem2_res.json()["data"]["id"]
    assert mem2_res.json()["data"]["status"] == "pending_review"

    # 4. Resolve using 'merge' strategy with consolidated text
    merged_text = "Prefers dynamic theme: light mode during daytime, dark mode at night"
    merge_res = await client.post(
        f"/api/v1/memories/{mem2_id}/resolve-conflict",
        json={
            "strategy": "merge",
            "merged_content": merged_text,
            "notes": "Contextual schedule clarification",
        },
        headers=headers,
    )
    assert merge_res.status_code == 200
    assert merge_res.json()["data"]["status"] == "approved"

    # Verify version was created, content updated, and old memory superseded
    async with core_db.async_session_factory() as db:
        m1 = (await db.execute(select(Memory).where(Memory.id == mem1_id))).scalar_one()
        assert m1.status == MemoryStatus.SUPERSEDED
        m2 = (await db.execute(select(Memory).where(Memory.id == mem2_id))).scalar_one()
        assert m2.content == merged_text
        versions = (
            (await db.execute(select(MemoryVersion).where(MemoryVersion.memory_id == mem2_id)))
            .scalars()
            .all()
        )
        assert len(versions) >= 1

    # 5. Ingest another conflicting candidate to test 'discard' strategy
    mem3_res = await client.post(
        "/api/v1/memories",
        json={"content": "Hates dark mode completely", "category": "preference"},
        headers=headers,
    )
    mem3_id = mem3_res.json()["data"]["id"]

    discard_res = await client.post(
        f"/api/v1/memories/{mem3_id}/resolve-conflict",
        json={"strategy": "discard", "notes": "Factually outdated statement."},
        headers=headers,
    )
    assert discard_res.status_code == 200
    assert discard_res.json()["data"]["status"] == "rejected"

    async with core_db.async_session_factory() as db:
        m3 = (await db.execute(select(Memory).where(Memory.id == mem3_id))).scalar_one()
        assert m3.status == MemoryStatus.REJECTED


@pytest.mark.asyncio
async def test_workspace_cmek_rotation_and_crypto_shredding(client: AsyncClient):
    """Verify Customer-Managed Encryption Key (CMEK) rotation and zero-knowledge crypto-shredding."""
    # 1. Register Owner
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "cmek_owner@phase28.ai",
            "password": "Password123!",
            "full_name": "CMEK Owner",
            "workspace_name": "CMEK Security WS",
        },
    )
    token = reg.json()["data"]["tokens"]["access_token"]
    ws_id = reg.json()["data"]["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # 2. Store workspace secrets
    sec1 = await client.post(
        f"/api/v1/workspaces/{ws_id}/secrets",
        json={"name": "OPENAI_API_KEY", "value": "sk-proj-live-prod-secret-key-12345"},
        headers=headers,
    )
    assert sec1.status_code == 201

    sec2 = await client.post(
        f"/api/v1/workspaces/{ws_id}/secrets",
        json={"name": "STRIPE_SECRET_KEY", "value": "sk_live_stripe_payment_secret_99999"},
        headers=headers,
    )
    assert sec2.status_code == 201

    # 3. Rotate CMEK key version
    rotate_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/cmek/rotate",
        headers=headers,
    )
    assert rotate_res.status_code == 200
    rot_data = rotate_res.json()["data"]
    assert rot_data["previous_key_version"] == 1
    assert rot_data["new_key_version"] == 2
    assert rot_data["reencrypted_secrets_count"] == 2

    # 4. List secrets after rotation -> decrypts transparently
    list_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/secrets",
        headers=headers,
    )
    assert list_res.status_code == 200
    secrets_list = list_res.json()["data"]
    assert len(secrets_list) == 2
    assert any(s["name"] == "OPENAI_API_KEY" for s in secrets_list)

    # 5. Zero-Knowledge Crypto-Shredding (Permanent destruction of workspace secrets)
    shred_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/cmek/crypto-shred",
        headers=headers,
    )
    assert shred_res.status_code == 200
    shred_data = shred_res.json()["data"]
    assert shred_data["status"] == "crypto_shredded"
    assert shred_data["shredded_secrets_count"] == 2

    # Verify secrets now return shredded indicators and raw ciphertexts are destroyed
    post_shred_list = await client.get(
        f"/api/v1/workspaces/{ws_id}/secrets",
        headers=headers,
    )
    assert post_shred_list.status_code == 200
    shredded_items = post_shred_list.json()["data"]
    for s in shredded_items:
        assert "[SHREDDED]" in s["masked_value"]


@pytest.mark.asyncio
async def test_workspace_retrieval_and_intelligence_benchmark(client: AsyncClient):
    """Verify live calculation of retrieval performance, retention health, cache efficiency, and platform grade."""
    # 1. Register User & Workspace
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "benchmarker@phase28.ai",
            "password": "Password123!",
            "full_name": "Benchmark Tester",
            "workspace_name": "Benchmark WS",
        },
    )
    token = reg.json()["data"]["tokens"]["access_token"]
    ws_id = reg.json()["data"]["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # 2. Ingest sample memories
    for i in range(5):
        await client.post(
            "/api/v1/memories",
            json={
                "content": f"Architectural fact #{i} about cloud infrastructure",
                "category": "project",
                "importance": 8,
            },
            headers=headers,
        )

    # 3. Query benchmark telemetry endpoint
    bench_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/benchmark",
        headers=headers,
    )
    assert bench_res.status_code == 200
    data = bench_res.json()["data"]

    assert data["workspace_id"] == ws_id
    assert data["total_memories"] >= 5
    assert data["active_memories"] >= 5
    assert data["conflict_resolution_rate"] == 1.0

    # Retention health
    retention = data["retention_health"]
    assert retention["strong_count"] >= 5
    assert retention["retention_health_index"] >= 0.70

    # Retrieval performance
    retrieval = data["retrieval_performance"]
    assert retrieval["hnsw_accelerated"] is True
    assert retrieval["query_latency_ms"] >= 0.0

    # Cache efficiency
    cache = data["cache_efficiency"]
    assert "hit_count" in cache
    assert "miss_count" in cache

    # Overall grade
    assert data["platform_grade"] in ("A+", "A")


@pytest.mark.asyncio
async def test_phase28_rbac_and_multi_tenant_boundaries(client: AsyncClient):
    """Verify strict multi-tenant boundaries and role authorizations on CMEK, shredding, and resolution."""
    # 1. Register Tenant A (Owner) and Tenant B (Unauthorized Member)
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner_a@phase28.ai",
            "password": "Password123!",
            "full_name": "Owner A",
            "workspace_name": "Tenant A WS",
        },
    )
    token_a = reg_a.json()["data"]["tokens"]["access_token"]
    ws_a = reg_a.json()["data"]["workspace"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-ID": ws_a}

    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "member_b@phase28.ai",
            "password": "Password123!",
            "full_name": "Member B",
            "workspace_name": "Tenant B WS",
        },
    )
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    user_b_id = reg_b.json()["data"]["user"]["id"]
    ws_b = reg_b.json()["data"]["workspace"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_b}

    # Add Member B to Workspace A with unprivileged 'member' role
    await client.post(
        f"/api/v1/workspaces/{ws_a}/members",
        json={"user_id": user_b_id, "role": "member"},
        headers=headers_a,
    )
    headers_b_in_a = {"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_a}

    # 2. Member B attempts to rotate CMEK in Workspace A -> 403 Forbidden
    rotate_res = await client.post(
        f"/api/v1/workspaces/{ws_a}/cmek/rotate",
        headers=headers_b_in_a,
    )
    assert rotate_res.status_code == 403

    # 3. Member B attempts to crypto-shred Workspace A -> 403 Forbidden
    shred_res = await client.post(
        f"/api/v1/workspaces/{ws_a}/cmek/crypto-shred",
        headers=headers_b_in_a,
    )
    assert shred_res.status_code == 403

    # 4. User B attempts to access Workspace A benchmark using Tenant B header -> 404
    foreign_res = await client.get(
        f"/api/v1/workspaces/{ws_a}/benchmark",
        headers=headers_b,
    )
    assert foreign_res.status_code == 404
