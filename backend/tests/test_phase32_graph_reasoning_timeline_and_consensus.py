from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core import database as core_db
from app.models.graph import EntityType, GraphEntity, GraphRelationship
from app.models.memory import Memory, MemoryCategory


@pytest.mark.asyncio
async def test_graph_multi_hop_path_reasoning(client: AsyncClient):
    """Verify GraphReasoningEngine discovers multi-hop explanatory paths between entities with path strength ranking."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "graphreasoner@phase32.ai",
            "password": "Password123!",
            "full_name": "Graph Reasoner",
            "workspace_name": "Reasoning WS",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # Seed 4 connected graph entities
    async with core_db.AsyncSessionLocal() as session:
        e1 = GraphEntity(workspace_id=ws_id, name="Project Apollo", entity_type=EntityType.PROJECT)
        e2 = GraphEntity(
            workspace_id=ws_id, name="FastAPI Backend", entity_type=EntityType.TECHNOLOGY
        )
        e3 = GraphEntity(
            workspace_id=ws_id, name="PostgreSQL Database", entity_type=EntityType.TECHNOLOGY
        )
        e4 = GraphEntity(
            workspace_id=ws_id, name="AWS RDS Cluster", entity_type=EntityType.LOCATION
        )
        session.add_all([e1, e2, e3, e4])
        await session.commit()
        await session.refresh(e1)
        await session.refresh(e2)
        await session.refresh(e3)
        await session.refresh(e4)

        r1 = GraphRelationship(
            workspace_id=ws_id,
            source_entity_id=e1.id,
            target_entity_id=e2.id,
            relationship_type="BUILT_WITH",
            weight=1.0,
        )
        r2 = GraphRelationship(
            workspace_id=ws_id,
            source_entity_id=e2.id,
            target_entity_id=e3.id,
            relationship_type="USES",
            weight=0.9,
        )
        r3 = GraphRelationship(
            workspace_id=ws_id,
            source_entity_id=e3.id,
            target_entity_id=e4.id,
            relationship_type="RUNS_ON",
            weight=1.0,
        )
        session.add_all([r1, r2, r3])
        await session.commit()

    # Query reasoning paths from "Project Apollo" to "AWS RDS Cluster"
    resp = await client.post(
        "/api/v1/graph/reasoning/find-paths",
        json={
            "source_entity": "Project Apollo",
            "target_entity": "AWS RDS Cluster",
            "max_depth": 4,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    res_data = resp.json()["data"]
    assert res_data["total_paths_found"] >= 1
    path = res_data["paths"][0]
    assert path["path_length"] == 3
    assert path["entities"] == [
        "Project Apollo",
        "FastAPI Backend",
        "PostgreSQL Database",
        "AWS RDS Cluster",
    ]
    assert path["relationships"] == ["BUILT_WITH", "USES", "RUNS_ON"]
    assert path["path_strength"] > 0.0
    assert "Project Apollo [BUILT_WITH] -> FastAPI Backend" in path["explanation"]
    assert "PostgreSQL Database [RUNS_ON] -> AWS RDS Cluster" in path["explanation"]


@pytest.mark.asyncio
async def test_graph_transitive_relationship_inference(client: AsyncClient):
    """Verify GraphReasoningEngine discovers transitive relationship hypotheses where direct edges do not exist."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "infertester@phase32.ai",
            "password": "Password123!",
            "full_name": "Inference Tester",
            "workspace_name": "Inference WS",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # Seed 3 entities in a transitive chain: Auth Service -> Redis Cache -> VPC Subnet
    async with core_db.AsyncSessionLocal() as session:
        e1 = GraphEntity(workspace_id=ws_id, name="Auth Service", entity_type=EntityType.TECHNOLOGY)
        e2 = GraphEntity(workspace_id=ws_id, name="Redis Cache", entity_type=EntityType.TECHNOLOGY)
        e3 = GraphEntity(workspace_id=ws_id, name="Private VPC", entity_type=EntityType.LOCATION)
        session.add_all([e1, e2, e3])
        await session.commit()
        await session.refresh(e1)
        await session.refresh(e2)
        await session.refresh(e3)

        r1 = GraphRelationship(
            workspace_id=ws_id,
            source_entity_id=e1.id,
            target_entity_id=e2.id,
            relationship_type="DEPENDS_ON",
            weight=1.0,
        )
        r2 = GraphRelationship(
            workspace_id=ws_id,
            source_entity_id=e2.id,
            target_entity_id=e3.id,
            relationship_type="DEPENDS_ON",
            weight=1.0,
        )
        session.add_all([r1, r2])
        await session.commit()

    # Query transitive inference
    resp = await client.post(
        "/api/v1/graph/reasoning/infer-relations",
        json={"min_confidence": 0.4, "limit": 10},
        headers=headers,
    )
    assert resp.status_code == 200
    res_data = resp.json()["data"]
    assert res_data["total_hypotheses"] >= 1
    hyp = res_data["inferred_relationships"][0]
    assert hyp["source_entity_name"] == "Auth Service"
    assert hyp["target_entity_name"] == "Private VPC"
    assert hyp["inferred_type"] in ("INDIRECTLY_DEPENDS_ON", "CONNECTED_TO")
    assert hyp["confidence"] >= 0.4
    assert len(hyp["evidence_hops"]) == 2


@pytest.mark.asyncio
async def test_temporal_timeline_time_travel_snapshot(client: AsyncClient):
    """Verify TimelineService reconstructs the exact active memory state at any arbitrary historical timestamp."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "timetravel@phase32.ai",
            "password": "Password123!",
            "full_name": "Time Traveler",
            "workspace_name": "Time WS",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    u_id = auth_data["user"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    now_dt = datetime.now(UTC)
    t_30d_ago = now_dt - timedelta(days=30)
    t_15d_ago = now_dt - timedelta(days=15)
    t_1d_ago = now_dt - timedelta(days=1)

    async with core_db.AsyncSessionLocal() as session:
        # Memory 1 created 30 days ago
        m1 = Memory(
            workspace_id=ws_id,
            user_id=u_id,
            content="Initial architecture uses monolithic Django stack",
            category=MemoryCategory.PROJECT,
            importance=7,
            created_at=t_30d_ago,
        )
        session.add(m1)
        await session.commit()
        await session.refresh(m1)

        # Memory 2 created 15 days ago
        m2 = Memory(
            workspace_id=ws_id,
            user_id=u_id,
            content="Team adopts TypeScript React frontend",
            category=MemoryCategory.PREFERENCE,
            importance=8,
            created_at=t_15d_ago,
        )
        session.add(m2)
        await session.commit()

        # Memory 3 created 1 day ago, superseding Memory 1
        m3 = Memory(
            workspace_id=ws_id,
            user_id=u_id,
            content="Architecture migrated from Django to FastAPI microservices",
            category=MemoryCategory.PROJECT,
            importance=9,
            created_at=t_1d_ago,
        )
        session.add(m3)
        await session.commit()
        await session.refresh(m3)

        # Mark m1 superseded by m3
        m1.superseded_by = m3.id
        await session.commit()

    # Time-travel to 20 days ago (between m1 and m2)
    t_20d_ago = now_dt - timedelta(days=20)
    resp_20d = await client.get(
        f"/api/v1/workspaces/{ws_id}/timeline/time-travel?as_of={t_20d_ago.isoformat()}",
        headers=headers,
    )
    assert resp_20d.status_code == 200
    snap_20d = resp_20d.json()["data"]
    assert snap_20d["active_memory_count"] == 1
    assert snap_20d["memories"][0]["content"] == "Initial architecture uses monolithic Django stack"

    # Time-travel to 10 days ago (between m2 and m3)
    t_10d_ago = now_dt - timedelta(days=10)
    resp_10d = await client.get(
        f"/api/v1/workspaces/{ws_id}/timeline/time-travel?as_of={t_10d_ago.isoformat()}",
        headers=headers,
    )
    assert resp_10d.status_code == 200
    snap_10d = resp_10d.json()["data"]
    assert snap_10d["active_memory_count"] == 2
    contents_10d = {m["content"] for m in snap_10d["memories"]}
    assert "Initial architecture uses monolithic Django stack" in contents_10d
    assert "Team adopts TypeScript React frontend" in contents_10d

    # Time-travel to present (m1 superseded, m2 and m3 active)
    resp_now = await client.get(
        f"/api/v1/workspaces/{ws_id}/timeline/time-travel?as_of={now_dt.isoformat()}",
        headers=headers,
    )
    assert resp_now.status_code == 200
    snap_now = resp_now.json()["data"]
    assert snap_now["active_memory_count"] == 2
    contents_now = {m["content"] for m in snap_now["memories"]}
    assert "Architecture migrated from Django to FastAPI microservices" in contents_now
    assert "Team adopts TypeScript React frontend" in contents_now


@pytest.mark.asyncio
async def test_temporal_timeline_diff_between_points_in_time(client: AsyncClient):
    """Verify TimelineService computes fine-grained structural deltas between two historical timestamps."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "timelinediff@phase32.ai",
            "password": "Password123!",
            "full_name": "Diff Tester",
            "workspace_name": "Diff WS",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    u_id = auth_data["user"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    now_dt = datetime.now(UTC)
    t_old = now_dt - timedelta(days=20)
    t_mid = now_dt - timedelta(days=10)

    async with core_db.AsyncSessionLocal() as session:
        m1 = Memory(
            workspace_id=ws_id,
            user_id=u_id,
            content="Deployments run manually via bash script",
            category=MemoryCategory.PROJECT,
            importance=6,
            created_at=t_old,
        )
        session.add(m1)
        await session.commit()
        await session.refresh(m1)

        m2 = Memory(
            workspace_id=ws_id,
            user_id=u_id,
            content="CI/CD automated with GitHub Actions and Docker containers",
            category=MemoryCategory.PROJECT,
            importance=9,
            created_at=now_dt - timedelta(days=5),
        )
        session.add(m2)
        await session.commit()
        await session.refresh(m2)

        m1.superseded_by = m2.id
        await session.commit()

    diff_resp = await client.post(
        f"/api/v1/workspaces/{ws_id}/timeline/diff",
        json={
            "timestamp_a": t_mid.isoformat(),
            "timestamp_b": now_dt.isoformat(),
        },
        headers=headers,
    )
    assert diff_resp.status_code == 200
    diff_data = diff_resp.json()["data"]
    assert diff_data["memories_added_count"] == 1
    assert diff_data["memories_superseded_count"] == 1
    assert diff_data["net_change"] == 0
    assert "Timeline Delta" in diff_data["diff_summary"]


@pytest.mark.asyncio
async def test_multi_agent_consensus_debate_protocol(client: AsyncClient):
    """Verify ConsensusDebateEngine conducts multi-perspective agent deliberation with grounded synthesis."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "debatetester@phase32.ai",
            "password": "Password123!",
            "full_name": "Debate Tester",
            "workspace_name": "Debate WS",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    u_id = auth_data["user"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # Seed grounding memories
    async with core_db.AsyncSessionLocal() as session:
        m = Memory(
            workspace_id=ws_id,
            user_id=u_id,
            content="Platform standardizes on Redis cluster for distributed rate limiting and active session tokens",
            category=MemoryCategory.PROJECT,
            importance=8,
            tags=["redis", "cache", "sessions"],
        )
        session.add(m)
        await session.commit()

    # Trigger Consensus Debate
    resp = await client.post(
        "/api/v1/chat/consensus-debate",
        json={
            "topic": "Should we migrate from Redis cluster to SQLite for distributed rate limiting?",
            "rounds": 2,
            "include_grounding_memories": True,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    debate = resp.json()["data"]
    assert debate["workspace_id"] == ws_id
    assert debate["total_rounds"] == 2
    assert len(debate["turns"]) >= 4

    roles = [t["agent_role"] for t in debate["turns"]]
    assert "PROPONENT" in roles
    assert "SKEPTIC" in roles
    assert "ARBITRATOR" in roles

    assert debate["verdict"] in ("CONSENSUS_REACHED", "PARTIAL_CONSENSUS")
    assert debate["consensus_score"] >= 0.50
    assert len(debate["key_conclusions"]) >= 3
    assert len(debate["grounding_memory_ids"]) >= 1


@pytest.mark.asyncio
async def test_phase32_tenancy_and_rbac_isolation(client: AsyncClient):
    """Verify strict multi-tenant isolation prevents cross-workspace pathfinding, time-travel, and consensus inspection."""
    # Tenant A
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tenant_a_p32@phase32.ai",
            "password": "Password123!",
            "full_name": "Tenant A",
            "workspace_name": "Workspace A",
        },
    )
    assert reg_a.status_code == 201
    auth_a = reg_a.json()["data"]
    _token_a = auth_a["tokens"]["access_token"]
    ws_a_id = auth_a["workspace"]["id"]

    # Tenant B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tenant_b_p32@phase32.ai",
            "password": "Password123!",
            "full_name": "Tenant B",
            "workspace_name": "Workspace B",
        },
    )
    assert reg_b.status_code == 201
    auth_b = reg_b.json()["data"]
    token_b = auth_b["tokens"]["access_token"]
    ws_b_id = auth_b["workspace"]["id"]

    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_b_id}

    # Tenant B tries to query Tenant A's time-travel snapshot
    attack_tt = await client.get(
        f"/api/v1/workspaces/{ws_a_id}/timeline/time-travel?as_of={datetime.now(UTC).isoformat()}",
        headers=headers_b,
    )
    assert attack_tt.status_code in (403, 404)

    # Tenant B tries to query Tenant A's timeline diff
    attack_diff = await client.post(
        f"/api/v1/workspaces/{ws_a_id}/timeline/diff",
        json={
            "timestamp_a": (datetime.now(UTC) - timedelta(days=5)).isoformat(),
            "timestamp_b": datetime.now(UTC).isoformat(),
        },
        headers=headers_b,
    )
    assert attack_diff.status_code in (403, 404)
