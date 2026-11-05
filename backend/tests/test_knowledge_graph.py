import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_graph_extraction_and_ingestion(client: AsyncClient, auth_headers: dict):
    text = (
        "Project Orion is built with Python and FastAPI. "
        "It uses PostgreSQL with pgvector for vector search and deploys on Render."
    )

    res = await client.post(
        "/api/v1/graph/extract",
        json={"text": text},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["entities_created"] >= 3
    assert data["relationships_created"] >= 1

    entity_names = [e["name"].lower() for e in data["entities"]]
    assert any("python" in n for n in entity_names)
    assert any("postgresql" in n for n in entity_names)
    assert any("orion" in n for n in entity_names)


@pytest.mark.asyncio
async def test_entity_crud_lifecycle(client: AsyncClient, auth_headers: dict):
    # 1. Create custom entity
    create_res = await client.post(
        "/api/v1/graph/entities",
        json={
            "name": "Redis Sentinel",
            "entity_type": "technology",
            "description": "High-availability caching and pub-sub engine.",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    ent = create_res.json()["data"]
    assert ent["name"] == "Redis Sentinel"
    assert ent["entity_type"] == "technology"
    ent_id = ent["id"]

    # 2. Get entity
    get_res = await client.get(f"/api/v1/graph/entities/{ent_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["id"] == ent_id

    # 3. List entities
    list_res = await client.get("/api/v1/graph/entities?search=Sentinel", headers=auth_headers)
    assert list_res.status_code == 200
    items = list_res.json()["data"]["items"]
    assert len(items) >= 1
    assert items[0]["name"] == "Redis Sentinel"

    # 4. Update entity
    patch_res = await client.patch(
        f"/api/v1/graph/entities/{ent_id}",
        json={"description": "Updated HA caching engine description."},
        headers=auth_headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["data"]["description"] == "Updated HA caching engine description."

    # 5. Delete entity
    del_res = await client.delete(f"/api/v1/graph/entities/{ent_id}", headers=auth_headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Confirm 404
    get_after = await client.get(f"/api/v1/graph/entities/{ent_id}", headers=auth_headers)
    assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_relationship_creation_and_neighborhood(client: AsyncClient, auth_headers: dict):
    # Create Entity A (Person)
    res_a = await client.post(
        "/api/v1/graph/entities",
        json={"name": "Alice Architect", "entity_type": "person"},
        headers=auth_headers,
    )
    a_id = res_a.json()["data"]["id"]

    # Create Entity B (Project)
    res_b = await client.post(
        "/api/v1/graph/entities",
        json={"name": "Project Pegasus", "entity_type": "project"},
        headers=auth_headers,
    )
    b_id = res_b.json()["data"]["id"]

    # Create Relationship A -> B
    rel_res = await client.post(
        "/api/v1/graph/relationships",
        json={
            "source_entity_id": a_id,
            "target_entity_id": b_id,
            "relationship_type": "leads_project",
            "weight": 2.0,
        },
        headers=auth_headers,
    )
    assert rel_res.status_code == 201
    rel_data = rel_res.json()["data"]
    assert rel_data["relationship_type"] == "leads_project"
    rel_id = rel_data["id"]

    # Neighborhood subgraph query for Alice
    neigh_res = await client.get(f"/api/v1/graph/neighborhood/{a_id}", headers=auth_headers)
    assert neigh_res.status_code == 200
    neigh_data = neigh_res.json()["data"]
    assert neigh_data["total_nodes"] == 2
    assert neigh_data["total_edges"] == 1
    assert any(n["id"] == b_id for n in neigh_data["nodes"])

    # Delete Relationship
    del_rel = await client.delete(f"/api/v1/graph/relationships/{rel_id}", headers=auth_headers)
    assert del_rel.status_code == 200
    assert del_rel.json()["success"] is True


@pytest.mark.asyncio
async def test_graph_visualization_and_analytics(client: AsyncClient, auth_headers: dict):
    # Ingest text to populate graph
    await client.post(
        "/api/v1/graph/extract",
        json={"text": "Jane works with Bob on Project Titan using Docker and Kubernetes."},
        headers=auth_headers,
    )

    # 1. Full Graph Data
    graph_res = await client.get("/api/v1/graph", headers=auth_headers)
    assert graph_res.status_code == 200
    graph_data = graph_res.json()["data"]
    assert graph_data["total_nodes"] >= 2

    node = graph_data["nodes"][0]
    assert "name" in node
    assert "entity_type" in node
    assert "degree" in node

    # 2. Graph Analytics
    analytics_res = await client.get("/api/v1/graph/analytics", headers=auth_headers)
    assert analytics_res.status_code == 200
    analytics = analytics_res.json()["data"]
    assert analytics["total_entities"] >= 2
    assert "entity_type_breakdown" in analytics
    assert "top_central_entities" in analytics


@pytest.mark.asyncio
async def test_knowledge_graph_multi_tenant_isolation(client: AsyncClient, auth_headers: dict):
    # User A creates secret entity in Workspace A
    res_a = await client.post(
        "/api/v1/graph/entities",
        json={"name": "Confidential Algorithm Alpha", "entity_type": "concept"},
        headers=auth_headers,
    )
    ent_a_id = res_a.json()["data"]["id"]

    # Register User B in Workspace B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "graphuserb@memoryverse.ai",
            "password": "Password123!",
            "full_name": "Graph User B",
        },
    )
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    ws_b = reg_b.json()["data"]["workspace"]["id"]
    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-Workspace-ID": ws_b,
    }

    # User B cannot access User A's entity
    get_res = await client.get(f"/api/v1/graph/entities/{ent_a_id}", headers=headers_b)
    assert get_res.status_code == 404

    # User B's graph does not contain User A's entity
    graph_b = await client.get("/api/v1/graph", headers=headers_b)
    assert graph_b.status_code == 200
    nodes_b = [n["name"] for n in graph_b.json()["data"]["nodes"]]
    assert "Confidential Algorithm Alpha" not in nodes_b

    # User B cannot delete User A's entity
    del_res = await client.delete(f"/api/v1/graph/entities/{ent_a_id}", headers=headers_b)
    assert del_res.status_code == 404
