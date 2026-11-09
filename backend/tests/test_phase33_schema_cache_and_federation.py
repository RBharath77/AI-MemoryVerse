from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.ai.semantic_cache import SemanticCache
from app.core import database as core_db
from app.models.memory import Memory, MemoryCategory


@pytest.mark.asyncio
async def test_cognitive_schema_extraction_valid(client: AsyncClient):
    """Verify CognitiveSchemaEngine extracts typed JSON records conforming to JSON schema properties."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "schematester@phase33.ai",
            "password": "Password123!",
            "full_name": "Schema Tester",
            "workspace_name": "Schema WS",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    unstructured_adr = """# Architecture Decision Record
Title: Adopt ClickHouse for Analytics Storage
Status: ACCEPTED
Priority: 8
Is Critical: true
Tags: clickhouse, analytics, timeseries
Author: Data Platform Team
"""

    target_schema = {
        "title": "ArchitectureDecisionRecord",
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "status": {"type": "string", "enum": ["PROPOSED", "ACCEPTED", "REJECTED"]},
            "priority": {"type": "integer"},
            "is_critical": {"type": "boolean"},
            "tags": {"type": "array"},
        },
        "required": ["title", "status", "priority", "is_critical"],
    }

    resp = await client.post(
        "/api/v1/documents/extract-schema",
        json={
            "content": unstructured_adr,
            "schema_definition": target_schema,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    res_data = resp.json()["data"]
    assert res_data["is_valid"] is True
    assert res_data["title"] == "ArchitectureDecisionRecord"

    extracted = res_data["extracted_data"]
    assert extracted["title"] == "Adopt ClickHouse for Analytics Storage"
    assert extracted["status"] == "ACCEPTED"
    assert extracted["priority"] == 8
    assert extracted["is_critical"] is True
    assert "clickhouse" in extracted["tags"]
    assert len(res_data["validation_errors"]) == 0


@pytest.mark.asyncio
async def test_cognitive_schema_extraction_validation_errors(client: AsyncClient):
    """Verify CognitiveSchemaEngine reports missing required properties and enum violations."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "schemaerr@phase33.ai",
            "password": "Password123!",
            "full_name": "Schema Error Tester",
            "workspace_name": "Schema Error WS",
        },
    )
    assert reg.status_code == 201
    token = reg.json()["data"]["tokens"]["access_token"]
    ws_id = reg.json()["data"]["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # Missing required 'title' and invalid status 'UNKNOWN'
    content = """Status: UNKNOWN
Priority: 5
"""
    target_schema = {
        "title": "StrictDoc",
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "status": {"type": "string", "enum": ["DRAFT", "PUBLISHED"]},
            "priority": {"type": "integer"},
        },
        "required": ["title", "status"],
    }

    resp = await client.post(
        "/api/v1/documents/extract-schema",
        json={"content": content, "schema_definition": target_schema},
        headers=headers,
    )
    assert resp.status_code == 200
    res_data = resp.json()["data"]
    assert res_data["is_valid"] is False
    assert any("title" in err for err in res_data["validation_errors"])
    assert any("status" in err for err in res_data["validation_errors"])


@pytest.mark.asyncio
async def test_semantic_cache_dependency_tracking_and_selective_invalidation(client: AsyncClient):
    """Verify SemanticCache dependency graph tracks citations and selectively invalidates only dependent queries."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "cachetester@phase33.ai",
            "password": "Password123!",
            "full_name": "Cache Tester",
            "workspace_name": "Cache WS",
        },
    )
    assert reg.status_code == 201
    token = reg.json()["data"]["tokens"]["access_token"]
    ws_id = reg.json()["data"]["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # 1. Clear cache and seed two queries with distinct dependencies
    SemanticCache.clear()

    q1 = "What is our primary database architecture?"
    ans1 = "The database uses PostgreSQL with read-replicas."
    cits1 = [{"id": "mem-pg-01", "title": "PostgreSQL Architecture"}]
    SemanticCache.set(workspace_id=ws_id, query=q1, content=ans1, citations=cits1)

    q2 = "What are the frontend styling standards?"
    ans2 = "The frontend utilizes Tailwind CSS with shadcn components."
    cits2 = [{"id": "mem-tw-02", "title": "Tailwind Conventions"}]
    SemanticCache.set(workspace_id=ws_id, query=q2, content=ans2, citations=cits2)

    # 2. Check cache freshness telemetry via API
    fresh_resp = await client.get(
        f"/api/v1/workspaces/{ws_id}/cache/freshness",
        headers=headers,
    )
    assert fresh_resp.status_code == 200
    fresh_data = fresh_resp.json()["data"]
    assert fresh_data["workspace_id"] == ws_id
    assert fresh_data["cached_entries"] == 2
    assert fresh_data["tracked_dependencies_count"] == 2

    # 3. Selectively invalidate only mem-pg-01
    inval_resp = await client.post(
        f"/api/v1/workspaces/{ws_id}/cache/invalidate-dependent",
        json={"dependency_ids": ["mem-pg-01"]},
        headers=headers,
    )
    assert inval_resp.status_code == 200
    inval_data = inval_resp.json()["data"]
    assert inval_data["invalidated_keys_count"] == 1
    assert inval_data["remaining_entries_count"] == 1

    # 4. Verify Q1 is invalidated while Q2 is preserved
    assert SemanticCache.get(ws_id, q1) is None
    hit2 = SemanticCache.get(ws_id, q2)
    assert hit2 is not None
    assert hit2[0] == ans2


@pytest.mark.asyncio
async def test_federated_multi_workspace_search(client: AsyncClient):
    """Verify FederatedSearchEngine retrieves and attributes memories across multiple authorized workspaces."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "federatedtester@phase33.ai",
            "password": "Password123!",
            "full_name": "Federated Tester",
            "workspace_name": "Frontend WS",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws1_id = auth_data["workspace"]["id"]
    u_id = auth_data["user"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws1_id}

    # Create a second workspace for the same user
    ws2_resp = await client.post(
        "/api/v1/workspaces",
        json={"name": "Backend WS", "description": "Backend Microservices"},
        headers=headers,
    )
    assert ws2_resp.status_code == 201
    ws2_id = ws2_resp.json()["data"]["id"]

    # Seed memory in Workspace 1
    async with core_db.AsyncSessionLocal() as session:
        m1 = Memory(
            workspace_id=ws1_id,
            user_id=u_id,
            content="React 19 Server Components and Next.js App Router client hydration patterns",
            category=MemoryCategory.PROJECT,
            importance=8,
            tags=["react", "nextjs", "frontend"],
        )
        # Seed memory in Workspace 2
        m2 = Memory(
            workspace_id=ws2_id,
            user_id=u_id,
            content="FastAPI asynchronous SQLAlchemy session pooling with PostgreSQL",
            category=MemoryCategory.PROJECT,
            importance=9,
            tags=["fastapi", "sqlalchemy", "postgres"],
        )
        session.add_all([m1, m2])
        await session.commit()

    # Perform federated search across both workspaces
    fed_resp = await client.post(
        "/api/v1/search/federated",
        json={
            "query": "React FastAPI architecture session patterns",
            "workspace_ids": [ws1_id, ws2_id],
            "top_k_per_workspace": 5,
            "include_memories": True,
            "include_documents": False,
        },
        headers=headers,
    )
    assert fed_resp.status_code == 200
    fed_data = fed_resp.json()["data"]
    assert fed_data["total_results"] >= 2
    assert len(fed_data["federated_workspaces_searched"]) == 2

    source_ws_ids = {r["source_workspace_id"] for r in fed_data["results"]}
    assert ws1_id in source_ws_ids
    assert ws2_id in source_ws_ids


@pytest.mark.asyncio
async def test_federated_search_unauthorized_workspace_rejected(client: AsyncClient):
    """Verify FederatedSearchEngine rejects queries containing workspaces the user is not a member of."""
    # Register Tenant A
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "user_a_p33@phase33.ai",
            "password": "Password123!",
            "full_name": "User A",
            "workspace_name": "Tenant A WS",
        },
    )
    assert reg_a.status_code == 201
    token_a = reg_a.json()["data"]["tokens"]["access_token"]
    ws_a_id = reg_a.json()["data"]["workspace"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-ID": ws_a_id}

    # Register Tenant B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "user_b_p33@phase33.ai",
            "password": "Password123!",
            "full_name": "User B",
            "workspace_name": "Tenant B WS",
        },
    )
    assert reg_b.status_code == 201
    ws_b_id = reg_b.json()["data"]["workspace"]["id"]

    # User A tries to federate search across WS A and WS B (which User A does not belong to)
    attack_resp = await client.post(
        "/api/v1/search/federated",
        json={
            "query": "Confidential financial plans",
            "workspace_ids": [ws_a_id, ws_b_id],
            "top_k_per_workspace": 5,
        },
        headers=headers_a,
    )
    assert attack_resp.status_code == 403
    assert f"'{ws_b_id}'" in attack_resp.json().get("detail", "") or "Access denied" in str(
        attack_resp.json()
    )


@pytest.mark.asyncio
async def test_phase33_cache_and_schema_tenancy_isolation(client: AsyncClient):
    """Verify strict multi-tenant isolation prevents cross-workspace cache telemetry and selective invalidation."""
    # Tenant A
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tenant_a_p33@phase33.ai",
            "password": "Password123!",
            "full_name": "Tenant A",
            "workspace_name": "Isolated A WS",
        },
    )
    assert reg_a.status_code == 201
    ws_a_id = reg_a.json()["data"]["workspace"]["id"]

    # Tenant B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tenant_b_p33@phase33.ai",
            "password": "Password123!",
            "full_name": "Tenant B",
            "workspace_name": "Isolated B WS",
        },
    )
    assert reg_b.status_code == 201
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    ws_b_id = reg_b.json()["data"]["workspace"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_b_id}

    # Tenant B attempts to inspect Tenant A's cache freshness
    attack_fresh = await client.get(
        f"/api/v1/workspaces/{ws_a_id}/cache/freshness",
        headers=headers_b,
    )
    assert attack_fresh.status_code in (403, 404)

    # Tenant B attempts to selectively invalidate Tenant A's cache
    attack_inval = await client.post(
        f"/api/v1/workspaces/{ws_a_id}/cache/invalidate-dependent",
        json={"dependency_ids": ["mem-123"]},
        headers=headers_b,
    )
    assert attack_inval.status_code in (403, 404)
