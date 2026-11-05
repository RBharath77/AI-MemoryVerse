import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_hybrid_search_retrieval(client: AsyncClient, auth_headers: dict):
    # 1. Create a memory
    await client.post(
        "/api/v1/memories",
        json={
            "content": "PostgreSQL with pgvector provides performant HNSW vector search.",
            "category": "semantic",
            "importance": 9,
            "tags": ["pgvector", "database", "search"],
        },
        headers=auth_headers,
    )

    # 2. Upload a document
    doc_content = (
        "# Hybrid Search Architecture\n\n"
        "Reciprocal Rank Fusion combines sparse lexical BM25 scores with dense vector similarities."
    )
    files = {"file": ("hybrid_search.md", io.BytesIO(doc_content.encode("utf-8")), "text/markdown")}
    await client.post("/api/v1/documents/upload", files=files, headers=auth_headers)

    # 3. Perform hybrid search
    res = await client.post(
        "/api/v1/search/hybrid",
        json={
            "query": "pgvector HNSW nearest neighbor",
            "top_k": 5,
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total_found"] >= 1
    assert any("pgvector" in item["content"] for item in data["results"])
    top_item = data["results"][0]
    assert top_item["score"] > 0.0


@pytest.mark.asyncio
async def test_conversation_crud_lifecycle(client: AsyncClient, auth_headers: dict):
    # 1. Create conversation
    create_res = await client.post(
        "/api/v1/chat/conversations",
        json={
            "title": "Architecture Q&A Session",
            "model": "gpt-4o-mini",
            "temperature": 0.5,
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    conv = create_res.json()["data"]
    assert conv["title"] == "Architecture Q&A Session"
    assert conv["model"] == "gpt-4o-mini"
    conv_id = conv["id"]

    # 2. List conversations
    list_res = await client.get("/api/v1/chat/conversations", headers=auth_headers)
    assert list_res.status_code == 200
    items = list_res.json()["data"]["items"]
    assert any(c["id"] == conv_id for c in items)

    # 3. Get single conversation
    get_res = await client.get(f"/api/v1/chat/conversations/{conv_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["id"] == conv_id

    # 4. Delete conversation
    del_res = await client.delete(f"/api/v1/chat/conversations/{conv_id}", headers=auth_headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Confirm 404
    get_after = await client.get(f"/api/v1/chat/conversations/{conv_id}", headers=auth_headers)
    assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_rag_message_with_grounded_citations(client: AsyncClient, auth_headers: dict):
    # Seed knowledge context
    await client.post(
        "/api/v1/memories",
        json={
            "content": "The production database runs PostgreSQL 16 on Render managed cloud.",
            "category": "project",
            "importance": 8,
        },
        headers=auth_headers,
    )

    # Create new conversation
    conv_res = await client.post(
        "/api/v1/chat/conversations",
        json={"title": "New Conversation"},
        headers=auth_headers,
    )
    conv_id = conv_res.json()["data"]["id"]

    # Send user question
    msg_res = await client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        json={"content": "What database version and hosting are we using?"},
        headers=auth_headers,
    )
    assert msg_res.status_code == 200
    msg_data = msg_res.json()["data"]
    assert msg_data["role"] == "assistant"
    assert len(msg_data["content"]) > 5
    assert len(msg_data["citations"]) >= 1

    citation = msg_data["citations"][0]
    assert "source_type" in citation
    assert "marker" in citation
    assert "title" in citation

    # Verify conversation title auto-updated from "New Conversation"
    conv_check = await client.get(f"/api/v1/chat/conversations/{conv_id}", headers=auth_headers)
    assert conv_check.json()["data"]["title"] != "New Conversation"

    # Message feedback
    fb_res = await client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages/{msg_data['id']}/feedback",
        json={"rating": 1},
        headers=auth_headers,
    )
    assert fb_res.status_code == 200
    assert fb_res.json()["data"]["feedback"] == 1


@pytest.mark.asyncio
async def test_streaming_chat_response(client: AsyncClient, auth_headers: dict):
    conv_res = await client.post("/api/v1/chat/conversations", json={}, headers=auth_headers)
    conv_id = conv_res.json()["data"]["id"]

    # Request streaming response
    stream_res = await client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        json={"content": "Explain vector search in one sentence.", "stream": True},
        headers=auth_headers,
    )
    assert stream_res.status_code == 200
    assert "text/event-stream" in stream_res.headers["content-type"]
    stream_text = stream_res.text
    assert "event: citations" in stream_text or "event: token" in stream_text


@pytest.mark.asyncio
async def test_chat_multi_tenant_isolation(client: AsyncClient, auth_headers: dict):
    # User A creates conversation
    conv_res = await client.post(
        "/api/v1/chat/conversations",
        json={"title": "Private User A Chat"},
        headers=auth_headers,
    )
    conv_id = conv_res.json()["data"]["id"]

    # Register User B in Workspace B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "chatuserb@memoryverse.ai",
            "password": "Password123!",
            "full_name": "Chat User B",
        },
    )
    token_b = reg_b.json()["data"]["tokens"]["access_token"]
    ws_b = reg_b.json()["data"]["workspace"]["id"]
    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-Workspace-ID": ws_b,
    }

    # User B cannot access User A's conversation
    get_res = await client.get(f"/api/v1/chat/conversations/{conv_id}", headers=headers_b)
    assert get_res.status_code == 404

    # User B cannot send messages to User A's conversation
    send_res = await client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        json={"content": "Intruder message"},
        headers=headers_b,
    )
    assert send_res.status_code == 404

    # User B cannot delete User A's conversation
    del_res = await client.delete(f"/api/v1/chat/conversations/{conv_id}", headers=headers_b)
    assert del_res.status_code == 404
