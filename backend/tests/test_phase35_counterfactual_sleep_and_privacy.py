from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core import database as core_db
from app.core.differential_privacy import DifferentialPrivacyEngine
from app.models.graph import EntityType, GraphEntity, GraphRelationship
from app.models.memory import Memory, MemoryCategory, MemoryStatus


@pytest.mark.asyncio
async def test_graph_counterfactual_simulation_ripple_and_tradeoffs(client: AsyncClient):
    """
    Test knowledge graph counterfactual 'what-if' simulation:
    traverses multi-hop dependency ripple effects, evaluates trade-offs, and calculates blast radius.
    """
    # 1. Register user and create workspace
    user_email = f"counterfactual_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "Simulation Scientist",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    # 2. Seed interconnected graph entities
    # A (PostgreSQL) -> B (SQLAlchemy) -> C (FastAPI Service)
    async with core_db.AsyncSessionLocal() as session:
        e1 = GraphEntity(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            name="PostgreSQL Database",
            entity_type=EntityType.TECHNOLOGY,
            description="Primary relational persistence store",
        )
        e2 = GraphEntity(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            name="Async SQLAlchemy ORM",
            entity_type=EntityType.TECHNOLOGY,
            description="Object-relational mapping pipeline",
        )
        e3 = GraphEntity(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            name="FastAPI Service Layer",
            entity_type=EntityType.TECHNOLOGY,
            description="High-throughput asynchronous REST API endpoints",
        )
        session.add_all([e1, e2, e3])
        await session.flush()

        r1 = GraphRelationship(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            source_entity_id=e2.id,
            target_entity_id=e1.id,
            relationship_type="CONNECTS_TO",
            weight=1.0,
        )
        r2 = GraphRelationship(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            source_entity_id=e3.id,
            target_entity_id=e2.id,
            relationship_type="USES",
            weight=1.0,
        )
        session.add_all([r1, r2])
        await session.commit()

    # 3. Simulate counterfactual migration: PostgreSQL -> ClickHouse
    sim_res = await client.post(
        "/api/v1/graph/simulate-counterfactual",
        headers=headers,
        json={
            "scenario_text": "Migrate from PostgreSQL Database to ClickHouse for analytical queries",
            "target_entities": ["PostgreSQL Database"],
            "proposed_action": "MIGRATE",
            "replacement_target": "ClickHouse",
            "max_ripple_depth": 3,
        },
    )
    assert sim_res.status_code == 200
    sim_data = sim_res.json()["data"]
    assert sim_data["direct_impact_count"] >= 1
    assert sim_data["cascading_impact_count"] >= 1
    assert sim_data["blast_radius_score"] > 0.0
    assert len(sim_data["impacted_entities"]) >= 2
    assert len(sim_data["risks_and_tradeoffs"]) >= 1
    assert len(sim_data["recommended_preconditions"]) >= 1

    # Check risk contents
    risk_categories = [r["category"] for r in sim_data["risks_and_tradeoffs"]]
    assert "data_loss" in risk_categories or "performance" in risk_categories


@pytest.mark.asyncio
async def test_cognitive_sleep_cycle_simulation_and_utility_filtering(client: AsyncClient):
    """
    Test cognitive sleep-cycle pruning simulation:
    verifies utility function calculation, transient note eligibility, and pin protection.
    """
    user_email = f"sleep_user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "Sleep Researcher",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()["data"]
    token = auth_data["tokens"]["access_token"]
    user_id = auth_data["user"]["id"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    now_dt = datetime.now(UTC)
    old_time = now_dt - timedelta(days=25)

    # Ingest:
    # 1. Transient scratchpad note (low importance) -> should be candidate
    # 2. Old dormant memory (low importance) -> should be candidate
    # 3. Pinned memory -> MUST be protected
    # 4. Critical importance memory (importance=10) -> MUST be protected
    async with core_db.AsyncSessionLocal() as session:
        m1 = Memory(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            user_id=user_id,
            content="Quick scratchpad: check server port 8000 tomorrow morning",
            category=MemoryCategory.EPISODIC,
            status=MemoryStatus.APPROVED,
            importance=3,
            is_pinned=False,
            tags=["scratchpad", "transient"],
            created_at=now_dt,
        )
        m2 = Memory(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            user_id=user_id,
            content="Dormant note from previous sprint regarding staging server IP",
            category=MemoryCategory.EPISODIC,
            status=MemoryStatus.APPROVED,
            importance=4,
            is_pinned=False,
            tags=["staging"],
            created_at=old_time,
        )
        m3 = Memory(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            user_id=user_id,
            content="CRITICAL: Zero-Trust Master Tenancy Isolation Rule",
            category=MemoryCategory.SEMANTIC,
            status=MemoryStatus.APPROVED,
            importance=5,
            is_pinned=True,  # Pinned
            tags=["core", "security"],
            created_at=old_time,
        )
        m4 = Memory(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            user_id=user_id,
            content="Production Database Root Encryption Key Rotation Standard",
            category=MemoryCategory.SEMANTIC,
            status=MemoryStatus.APPROVED,
            importance=10,  # Max importance
            is_pinned=False,
            tags=["cmek", "security"],
            created_at=old_time,
        )
        session.add_all([m1, m2, m3, m4])
        await session.commit()

        pinned_id = m3.id
        important_id = m4.id

    # Simulate sleep cycle
    sim_res = await client.post(
        "/api/v1/memories/sleep-cycle/simulate",
        headers=headers,
        json={
            "utility_threshold": 0.35,
            "inactivity_days": 14,
            "protect_pinned": True,
            "protect_graph_connected": True,
        },
    )
    assert sim_res.status_code == 200
    sim_data = sim_res.json()["data"]
    assert sim_data["total_active_memories"] >= 4
    assert sim_data["candidates_identified"] >= 1
    assert sim_data["protected_count"] >= 2
    assert sim_data["estimated_token_savings"] > 0

    candidate_ids = [c["memory_id"] for c in sim_data["candidates"]]
    assert pinned_id not in candidate_ids
    assert important_id not in candidate_ids


@pytest.mark.asyncio
async def test_cognitive_sleep_cycle_execution_archive_and_compact(client: AsyncClient):
    """
    Test sleep-cycle execution with 'COMPACT' action:
    combines candidate memories into a single consolidated digest and archives originals.
    """
    user_email = f"compact_user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "Compaction Architect",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()["data"]
    token = auth_data["tokens"]["access_token"]
    user_id = auth_data["user"]["id"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    # Ingest 3 transient candidate memories
    mem_ids = []
    async with core_db.AsyncSessionLocal() as session:
        for idx in range(3):
            m = Memory(
                id=str(uuid.uuid4()),
                workspace_id=ws_id,
                user_id=user_id,
                content=f"Transient note #{idx + 1} regarding legacy prototype endpoint v0.{idx}",
                category=MemoryCategory.EPISODIC,
                status=MemoryStatus.APPROVED,
                importance=2,
                tags=["transient"],
            )
            session.add(m)
            mem_ids.append(m.id)
        await session.commit()

    # Execute sleep cycle with COMPACT
    exec_res = await client.post(
        "/api/v1/memories/sleep-cycle/execute",
        headers=headers,
        json={
            "candidate_memory_ids": mem_ids,
            "action": "COMPACT",
            "compaction_title": "Sprint Prototype Archive Digest",
        },
    )
    assert exec_res.status_code == 200
    exec_data = exec_res.json()["data"]
    assert exec_data["action_executed"] == "COMPACT"
    assert exec_data["processed_count"] == 3
    assert exec_data["compacted_memory_id"] is not None
    compacted_id = exec_data["compacted_memory_id"]

    # Verify compacted digest memory exists
    digest_res = await client.get(f"/api/v1/memories/{compacted_id}", headers=headers)
    assert digest_res.status_code == 200
    digest_data = digest_res.json()["data"]
    assert "Sprint Prototype Archive Digest" in digest_data["content"]
    assert "sleep_cycle" in digest_data["tags"]
    assert digest_data["category"] == "semantic"

    # Verify original memories are now ARCHIVED
    async with core_db.AsyncSessionLocal() as session:
        for mid in mem_ids:
            mem = await session.get(Memory, mid)
            assert mem is not None
            assert mem.status == MemoryStatus.ARCHIVED
            assert mem.superseded_by == compacted_id


@pytest.mark.asyncio
async def test_differentially_private_metrics_noise_and_laplace_properties(client: AsyncClient):
    """
    Test Differential Privacy Engine:
    verifies Laplace and Gaussian mathematical noise sampling and differentially private endpoint outputs.
    """
    # 1. Pure mathematical sampling assertions
    laplace_noise_1 = DifferentialPrivacyEngine.sample_laplace_noise(scale=1.0)
    assert isinstance(laplace_noise_1, float)

    gaussian_noise_1 = DifferentialPrivacyEngine.sample_gaussian_noise(
        sensitivity=1.0, epsilon=1.0, delta=1e-5
    )
    assert isinstance(gaussian_noise_1, float)

    # Zero scale yields zero noise
    assert DifferentialPrivacyEngine.sample_laplace_noise(scale=0.0) == 0.0

    # 2. Register user and workspace
    user_email = f"dp_user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_email,
            "password": "SecurePassword123!",
            "full_name": "DP Statistician",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    # Ingest memories with various tags and categories
    tags_pool = [["fastapi", "python"], ["fastapi", "async"], ["security", "auth"], ["ui", "react"]]
    for idx, tags in enumerate(tags_pool):
        await client.post(
            "/api/v1/memories",
            headers=headers,
            json={
                "content": f"Differential privacy test memory item #{idx + 1}",
                "category": "semantic" if idx % 2 == 0 else "episodic",
                "importance": 6 + idx,
                "tags": tags,
            },
        )

    # 3. Query differentially private metrics with epsilon=1.0, delta=1e-5
    dp_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/privacy/differentially-private-metrics",
        headers=headers,
        json={
            "epsilon": 1.0,
            "delta": 1e-5,
            "metric_types": ["tag_distribution", "category_counts", "average_importance"],
        },
    )
    assert dp_res.status_code == 200
    dp_data = dp_res.json()["data"]
    assert dp_data["workspace_id"] == ws_id
    assert dp_data["epsilon_consumed"] == 1.0
    assert dp_data["delta"] == 1e-5
    assert dp_data["mechanism"] == "Laplace"
    assert dp_data["total_records_analyzed"] >= 4
    assert 1.0 <= dp_data["noisy_average_importance"] <= 10.0
    assert "Differential Privacy" in dp_data["privacy_guarantee"]
    assert len(dp_data["noisy_tag_distribution"]) >= 1


@pytest.mark.asyncio
async def test_privacy_budget_tracking_and_depletion(client: AsyncClient):
    """
    Test differential privacy budget accounting across repeated queries.
    """
    user_email = f"budget_user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "SecurePassword123!", "full_name": "Budget Auditor"},
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}

    initial_budget = DifferentialPrivacyEngine.get_workspace_consumed_budget(ws_id)

    # Query 1 with epsilon=1.5
    await client.post(
        f"/api/v1/workspaces/{ws_id}/privacy/differentially-private-metrics",
        headers=headers,
        json={"epsilon": 1.5, "delta": 1e-5},
    )
    budget_after_1 = DifferentialPrivacyEngine.get_workspace_consumed_budget(ws_id)
    assert budget_after_1 >= initial_budget + 1.49

    # Query 2 with epsilon=2.0
    await client.post(
        f"/api/v1/workspaces/{ws_id}/privacy/differentially-private-metrics",
        headers=headers,
        json={"epsilon": 2.0, "delta": 1e-5},
    )
    budget_after_2 = DifferentialPrivacyEngine.get_workspace_consumed_budget(ws_id)
    assert budget_after_2 >= budget_after_1 + 1.99


@pytest.mark.asyncio
async def test_phase35_multi_tenant_isolation(client: AsyncClient):
    """
    Verify complete multi-tenant isolation across counterfactual simulation,
    sleep-cycle pruning, and differential privacy metrics between Workspace A and Workspace B.
    """
    # 1. Workspace A
    user_a = f"tenant_a_p35_{uuid.uuid4().hex[:6]}@example.com"
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={"email": user_a, "password": "SecurePassword123!", "full_name": "Tenant A"},
    )
    assert reg_a.status_code == 201
    token_a = reg_a.json()["data"]["tokens"]["access_token"]
    ws_a = reg_a.json()["data"]["workspace"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-Id": ws_a}

    # Ingest private memory in Workspace A
    mem_a_res = await client.post(
        "/api/v1/memories",
        headers=headers_a,
        json={
            "content": "Proprietary Project Falcon Quantum Accelerator Architecture",
            "category": "semantic",
            "importance": 10,
            "tags": ["quantum", "falcon"],
        },
    )
    mem_a_id = mem_a_res.json()["data"]["id"]

    # 2. Workspace B
    user_b = f"tenant_b_p35_{uuid.uuid4().hex[:6]}@example.com"
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={"email": user_b, "password": "SecurePassword123!", "full_name": "Tenant B"},
    )
    assert reg_b.status_code == 201
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    ws_b = reg_b.json()["data"]["workspace"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-Id": ws_b}

    # 3. Tenant B attempts to run differential privacy on Workspace A -> 404 Forbidden
    cross_dp_res = await client.post(
        f"/api/v1/workspaces/{ws_a}/privacy/differentially-private-metrics",
        headers=headers_b,
        json={"epsilon": 1.0},
    )
    assert cross_dp_res.status_code == 404

    # 4. Tenant B attempts to execute sleep cycle on Tenant A's memory -> 0 processed
    cross_sleep_res = await client.post(
        "/api/v1/memories/sleep-cycle/execute",
        headers=headers_b,
        json={"candidate_memory_ids": [mem_a_id], "action": "ARCHIVE"},
    )
    assert cross_sleep_res.status_code == 200
    assert cross_sleep_res.json()["data"]["processed_count"] == 0

    # Verify Tenant A's memory remains untouched and APPROVED
    async with core_db.AsyncSessionLocal() as session:
        mem_a = await session.get(Memory, mem_a_id)
        assert mem_a is not None
        assert mem_a.status == MemoryStatus.APPROVED
