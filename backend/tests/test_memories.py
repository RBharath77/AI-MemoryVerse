import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_memories(client: AsyncClient, auth_headers: dict):
    payload = {
        "content": "Prefers concise, source-grounded answers with KaTeX math rendering.",
        "category": "preference",
        "importance": 8,
        "is_pinned": True,
        "tags": ["formatting", "math", "instructions"],
    }
    create_res = await client.post("/api/v1/memories", json=payload, headers=auth_headers)
    assert create_res.status_code == 201
    body = create_res.json()
    assert body["success"] is True
    memory = body["data"]
    assert memory["content"] == payload["content"]
    assert memory["category"] == "preference"
    assert memory["importance"] == 8
    assert memory["is_pinned"] is True

    memory_id = memory["id"]

    # List memories
    list_res = await client.get("/api/v1/memories", headers=auth_headers)
    assert list_res.status_code == 200
    list_body = list_res.json()
    assert list_body["success"] is True
    assert list_body["data"]["total"] >= 1
    assert any(m["id"] == memory_id for m in list_body["data"]["items"])


@pytest.mark.asyncio
async def test_filter_and_search_memories(client: AsyncClient, auth_headers: dict):
    # Add semantic memory
    await client.post(
        "/api/v1/memories",
        json={
            "content": "Project Apollo uses PostgreSQL with pgvector for HNSW indexing.",
            "category": "project",
        },
        headers=auth_headers,
    )
    # Add episodic memory
    await client.post(
        "/api/v1/memories",
        json={
            "content": "Met with Jane to align on Q3 RAG accuracy benchmarks.",
            "category": "episodic",
        },
        headers=auth_headers,
    )

    # Filter by category = project
    proj_res = await client.get("/api/v1/memories?category=project", headers=auth_headers)
    assert proj_res.status_code == 200
    items = proj_res.json()["data"]["items"]
    assert all(m["category"] == "project" for m in items)

    # Search keyword
    search_res = await client.get("/api/v1/memories?search=pgvector", headers=auth_headers)
    assert search_res.status_code == 200
    search_items = search_res.json()["data"]["items"]
    assert len(search_items) >= 1
    assert "pgvector" in search_items[0]["content"]


@pytest.mark.asyncio
async def test_update_and_delete_memory(client: AsyncClient, auth_headers: dict):
    create_res = await client.post(
        "/api/v1/memories",
        json={"content": "Initial fact statement", "category": "semantic"},
        headers=auth_headers,
    )
    memory_id = create_res.json()["data"]["id"]

    # Update content
    update_res = await client.patch(
        f"/api/v1/memories/{memory_id}",
        json={"content": "Updated verified fact statement", "importance": 9},
        headers=auth_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["data"]["content"] == "Updated verified fact statement"
    assert update_res.json()["data"]["importance"] == 9

    # Delete memory
    del_res = await client.delete(f"/api/v1/memories/{memory_id}", headers=auth_headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Confirm not found
    get_res = await client.get(f"/api/v1/memories/{memory_id}", headers=auth_headers)
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_memory_multi_tenant_isolation(client: AsyncClient, auth_headers: dict):
    # User A creates private memory
    create_res = await client.post(
        "/api/v1/memories",
        json={"content": "Confidential User A personal memory", "category": "semantic"},
        headers=auth_headers,
    )
    memory_a_id = create_res.json()["data"]["id"]

    # Register User B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "memoryuserb@memoryverse.ai",
            "password": "Password123!",
            "full_name": "User B",
        },
    )
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    ws_b = reg_b.json()["data"]["workspace"]["id"]
    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-Workspace-ID": ws_b,
    }

    # User B attempts to access User A's memory
    res = await client.get(f"/api/v1/memories/{memory_a_id}", headers=headers_b)
    assert res.status_code == 404
    assert res.json()["success"] is False
