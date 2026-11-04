import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_workspaces(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/workspaces", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) >= 1
    assert body["data"][0]["name"] == "Test Workspace"


@pytest.mark.asyncio
async def test_create_workspace(client: AsyncClient, auth_headers: dict):
    payload = {
        "name": "AI Research Lab",
        "description": "Multi-agent memory research",
    }
    response = await client.post("/api/v1/workspaces", json=payload, headers=auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["name"] == "AI Research Lab"
    assert "ai-research-lab" in body["data"]["slug"]


@pytest.mark.asyncio
async def test_workspace_isolation_between_users(client: AsyncClient, auth_headers: dict):
    # User A creates a workspace
    create_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "User A Private Vault", "description": "Top Secret"},
        headers=auth_headers,
    )
    workspace_a_id = create_res.json()["data"]["id"]

    # Register User B
    user_b_payload = {
        "email": "userb@memoryverse.ai",
        "password": "Password123!",
        "full_name": "User B",
    }
    reg_b = await client.post("/api/v1/auth/register", json=user_b_payload)
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User B attempts to access User A's workspace
    res = await client.get(f"/api/v1/workspaces/{workspace_a_id}", headers=headers_b)
    # Must be forbidden / not found
    assert res.status_code in [403, 404]
    assert res.json()["success"] is False


@pytest.mark.asyncio
async def test_workspace_member_addition(client: AsyncClient, auth_headers: dict):
    # Register member user
    member_payload = {
        "email": "teammate@memoryverse.ai",
        "password": "Password123!",
        "full_name": "Teammate",
    }
    reg_res = await client.post("/api/v1/auth/register", json=member_payload)
    member_user_id = reg_res.json()["data"]["user"]["id"]

    # Extract user A's workspace id from auth_headers
    workspace_id = auth_headers["X-Workspace-ID"]

    # Add member to User A's workspace
    add_payload = {
        "user_id": member_user_id,
        "role": "member",
    }
    res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json=add_payload,
        headers=auth_headers,
    )
    assert res.status_code == 201
    assert res.json()["success"] is True
    assert res.json()["data"]["user_id"] == member_user_id
    assert res.json()["data"]["role"] == "member"

