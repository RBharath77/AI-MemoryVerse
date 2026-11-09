from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_conversation_deletion_rbac(client: AsyncClient):
    """Verify that only the conversation creator, workspace admin, or owner can delete a conversation."""
    # 1. Register Owner
    reg_owner = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "chat_owner@phase13.ai",
            "password": "Password123!",
            "full_name": "Chat Owner",
            "workspace_name": "Chat Security WS",
        },
    )
    assert reg_owner.status_code == 201
    owner_token = reg_owner.json()["data"]["tokens"]["access_token"]
    ws_id = reg_owner.json()["data"]["workspace"]["id"]
    owner_headers = {"Authorization": f"Bearer {owner_token}", "X-Workspace-ID": ws_id}

    # 2. Register Member A (Creator)
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "chat_creator@phase13.ai",
            "password": "Password123!",
            "full_name": "Chat Creator",
        },
    )
    assert reg_a.status_code == 201
    user_a_id = reg_a.json()["data"]["user"]["id"]
    token_a = reg_a.json()["data"]["tokens"]["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-ID": ws_id}

    # 3. Register Member B (Unauthorized Member)
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "chat_unauth@phase13.ai",
            "password": "Password123!",
            "full_name": "Chat Unauth",
        },
    )
    assert reg_b.status_code == 201
    user_b_id = reg_b.json()["data"]["user"]["id"]
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_id}

    # Add both users as regular members
    for uid in [user_a_id, user_b_id]:
        add_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": uid, "role": "member"},
            headers=owner_headers,
        )
        assert add_res.status_code == 201

    # 4. Member A creates a conversation
    conv_res = await client.post(
        "/api/v1/chat/conversations",
        json={"title": "Private Architectural Discussion"},
        headers=headers_a,
    )
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["data"]["id"]

    # 5. Member B attempts to delete Member A's conversation -> 403 Forbidden
    del_res_b = await client.delete(
        f"/api/v1/chat/conversations/{conv_id}",
        headers=headers_b,
    )
    assert del_res_b.status_code == 403
    assert "Insufficient permissions" in del_res_b.text

    # 6. Member A (creator) deletes conversation -> 200 OK
    del_res_a = await client.delete(
        f"/api/v1/chat/conversations/{conv_id}",
        headers=headers_a,
    )
    assert del_res_a.status_code == 200
    assert "deleted successfully" in del_res_a.text


@pytest.mark.asyncio
async def test_memory_deletion_rbac(client: AsyncClient):
    """Verify that regular members cannot delete memories created by other users."""
    # 1. Register Owner
    reg_owner = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "mem_owner@phase13.ai",
            "password": "Password123!",
            "full_name": "Memory Owner",
            "workspace_name": "Memory Security WS",
        },
    )
    assert reg_owner.status_code == 201
    owner_token = reg_owner.json()["data"]["tokens"]["access_token"]
    ws_id = reg_owner.json()["data"]["workspace"]["id"]
    owner_headers = {"Authorization": f"Bearer {owner_token}", "X-Workspace-ID": ws_id}

    # 2. Register Member A (Creator) and Member B
    reg_a = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "mem_creator@phase13.ai",
            "password": "Password123!",
            "full_name": "Memory Creator",
        },
    )
    token_a = reg_a.json()["data"]["tokens"]["access_token"]
    user_a_id = reg_a.json()["data"]["user"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-ID": ws_id}

    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "mem_unauth@phase13.ai",
            "password": "Password123!",
            "full_name": "Memory Unauth",
        },
    )
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    user_b_id = reg_b.json()["data"]["user"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_id}

    for uid in [user_a_id, user_b_id]:
        await client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": uid, "role": "member"},
            headers=owner_headers,
        )

    # 3. Member A creates a memory
    mem_res = await client.post(
        "/api/v1/memories",
        json={"content": "Confidential memory note for Member A", "category": "project"},
        headers=headers_a,
    )
    assert mem_res.status_code == 201
    mem_id = mem_res.json()["data"]["id"]

    # 4. Member B attempts to delete Member A's memory -> 403 Forbidden
    del_res_b = await client.delete(
        f"/api/v1/memories/{mem_id}",
        headers=headers_b,
    )
    assert del_res_b.status_code == 403
    assert "Insufficient permissions" in del_res_b.text

    # 5. Member A deletes their own memory -> 200 OK
    del_res_a = await client.delete(
        f"/api/v1/memories/{mem_id}",
        headers=headers_a,
    )
    assert del_res_a.status_code == 200
    assert "deleted successfully" in del_res_a.text


@pytest.mark.asyncio
async def test_memory_link_self_reference_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify that creating a memory link pointing to the same memory is rejected with 400 Bad Request."""
    # 1. Create a memory
    mem_res = await client.post(
        "/api/v1/memories",
        json={"content": "Self reference test memory node", "category": "semantic"},
        headers=auth_headers,
    )
    assert mem_res.status_code == 201
    mem_id = mem_res.json()["data"]["id"]

    # 2. Attempt self-link
    link_res = await client.post(
        f"/api/v1/memories/{mem_id}/links",
        json={"target_memory_id": mem_id, "relationship_type": "supports"},
        headers=auth_headers,
    )
    assert link_res.status_code == 400
    assert "cannot be the same" in link_res.text


@pytest.mark.asyncio
async def test_memory_link_idempotency(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify that creating an identical link between two memories returns the existing link idempotently."""
    # 1. Create two memories
    m1 = await client.post(
        "/api/v1/memories",
        json={"content": "Primary architectural component A", "category": "semantic"},
        headers=auth_headers,
    )
    m2 = await client.post(
        "/api/v1/memories",
        json={"content": "Secondary architectural component B", "category": "semantic"},
        headers=auth_headers,
    )
    m1_id = m1.json()["data"]["id"]
    m2_id = m2.json()["data"]["id"]

    # 2. Create link
    link1 = await client.post(
        f"/api/v1/memories/{m1_id}/links",
        json={"target_memory_id": m2_id, "relationship_type": "depends_on"},
        headers=auth_headers,
    )
    assert link1.status_code == 200
    link1_id = link1.json()["data"]["id"]

    # 3. Create same link again -> should return existing link
    link2 = await client.post(
        f"/api/v1/memories/{m1_id}/links",
        json={"target_memory_id": m2_id, "relationship_type": "depends_on"},
        headers=auth_headers,
    )
    assert link2.status_code == 200
    assert link2.json()["data"]["id"] == link1_id


@pytest.mark.asyncio
async def test_memory_bulk_import_sanitization_and_bounding(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify bulk memory import sanitizes sensitive credentials and enforces array bounds."""
    # 1. Import with embedded credentials
    import_payload = {
        "memories": [
            {
                "content": "Production config with AWS AKIAIOSFODNN7EXAMPLE and OpenAI sk-proj-1234567890abcdef1234567890",
                "category": "project",
                "importance": 9,
                "tags": ["cloud", "credentials"],
            }
        ]
    }
    imp_res = await client.post(
        "/api/v1/memories/import",
        json=import_payload,
        headers=auth_headers,
    )
    assert imp_res.status_code == 200
    data = imp_res.json()["data"]
    assert data["imported_count"] == 1

    # 2. Query memories to verify redaction occurred
    list_res = await client.get("/api/v1/memories", headers=auth_headers)
    assert list_res.status_code == 200
    items = list_res.json()["data"]["items"]
    matching = [m for m in items if "Production config" in m["content"]]
    assert len(matching) == 1
    sanitized_content = matching[0]["content"]
    assert "AKIAIOSFODNN7EXAMPLE" not in sanitized_content
    assert "sk-proj-" not in sanitized_content
    assert "[REDACTED_AWS_KEY]" in sanitized_content
    assert "[REDACTED_OPENAI_KEY]" in sanitized_content

    # 3. Empty memories array rejected with 422
    empty_res = await client.post(
        "/api/v1/memories/import",
        json={"memories": []},
        headers=auth_headers,
    )
    assert empty_res.status_code == 422
