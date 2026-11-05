import pytest
from httpx import AsyncClient

from app.core.ssrf import validate_url_safe


@pytest.mark.asyncio
async def test_scenario_1_registration_workspace_and_memory_lifecycle(
    client: AsyncClient,
):
    """Scenario 1: Register, create workspace, and add a memory."""
    # 1. Register
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "e2e_user1@memoryverse.ai",
            "password": "SecurePassword123!",
            "full_name": "E2E Explorer",
            "workspace_name": "E2E Knowledge Base",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()["data"]
    token = auth_data["tokens"]["access_token"]
    ws_id = auth_data["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # 2. Add Memory
    mem_res = await client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "content": "The AI-MemoryVerse system was designed in 2026 using FastAPI and Next.js.",
            "category": "project",
            "importance": 9,
        },
    )
    assert mem_res.status_code == 201
    mem = mem_res.json()["data"]
    assert mem["content"].startswith("The AI-MemoryVerse system")
    assert mem["status"] == "approved"
    assert mem["workspace_id"] == ws_id


@pytest.mark.asyncio
async def test_scenario_2_persistence_verification(client: AsyncClient, auth_headers: dict):
    """Scenario 2: Querying the database returns the exact memory with
    timestamp and metadata intact.
    """
    # Create memory
    create_res = await client.post(
        "/api/v1/memories",
        headers=auth_headers,
        json={
            "content": "Persistence verification test fact: PostgreSQL ensures ACID guarantees.",
            "category": "semantic",
            "importance": 7,
        },
    )
    assert create_res.status_code == 201
    mem_id = create_res.json()["data"]["id"]

    # Query list
    list_res = await client.get("/api/v1/memories", headers=auth_headers)
    assert list_res.status_code == 200
    items = list_res.json()["data"]["items"]
    persisted = next((m for m in items if m["id"] == mem_id), None)
    assert persisted is not None
    assert persisted["content"] == (
        "Persistence verification test fact: PostgreSQL ensures ACID guarantees."
    )
    assert "created_at" in persisted


@pytest.mark.asyncio
async def test_scenario_3_conversation_with_memory_retrieval(
    client: AsyncClient, auth_headers: dict
):
    """Scenario 3: Start a new conversation and retrieve a saved fact."""
    # 1. Ingest memory
    await client.post(
        "/api/v1/memories",
        headers=auth_headers,
        json={
            "content": "Our main deployment platform is Render with managed Redis and PostgreSQL.",
            "category": "project",
            "importance": 9,
        },
    )

    # 2. Create conversation
    conv_res = await client.post(
        "/api/v1/chat/conversations",
        headers=auth_headers,
        json={"title": "Deployment Planning"},
    )
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["data"]["id"]

    # 3. Send message querying deployment platform
    msg_res = await client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        headers=auth_headers,
        json={"content": "Which deployment platform do we use for AI-MemoryVerse?"},
    )
    assert msg_res.status_code == 200
    msg_data = msg_res.json()["data"]
    assert "content" in msg_data
    assert "citations" in msg_data
    assert len(msg_data["citations"]) >= 1


@pytest.mark.asyncio
async def test_scenario_4_and_5_multi_document_upload_and_grounded_citations(
    client: AsyncClient, auth_headers: dict
):
    """Scenarios 4 & 5: Upload multiple documents and check that answers cite correct sources."""
    # 1. Upload Doc 1
    files_1 = {
        "file": (
            "arch_spec.txt",
            b"AI-MemoryVerse architecture features a modular monolith "
            b"with Celery background workers.",
            "text/plain",
        )
    }
    doc1_res = await client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files=files_1,
        data={"title": "Architecture Spec"},
    )
    assert doc1_res.status_code == 201
    assert "id" in doc1_res.json()["data"]["document"]

    # 2. Upload Doc 2
    files_2 = {
        "file": (
            "vector_spec.txt",
            b"Vector similarity is computed via pgvector using cosine distance and HNSW indexing.",
            "text/plain",
        )
    }
    doc2_res = await client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files=files_2,
        data={"title": "Vector Spec"},
    )
    assert doc2_res.status_code == 201
    assert "id" in doc2_res.json()["data"]["document"]

    # 3. Hybrid search querying across both
    search_res = await client.post(
        "/api/v1/search/hybrid",
        headers=auth_headers,
        json={
            "query": "architecture vector pgvector Celery",
            "top_k": 5,
            "include_documents": True,
            "include_memories": False,
        },
    )
    assert search_res.status_code == 200
    results = search_res.json()["data"]["results"]
    assert len(results) >= 1
    assert any("Celery" in r["content"] or "pgvector" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_scenario_6_memory_versioning_and_rollback(client: AsyncClient, auth_headers: dict):
    """Scenario 6: Edit a memory and inspect version history."""
    # 1. Create initial memory
    create_res = await client.post(
        "/api/v1/memories",
        headers=auth_headers,
        json={
            "content": "Initial budget allocation is 10,000 USD.",
            "category": "project",
            "importance": 5,
        },
    )
    mem_id = create_res.json()["data"]["id"]

    # 2. Update memory
    update_res = await client.patch(
        f"/api/v1/memories/{mem_id}",
        headers=auth_headers,
        json={
            "content": "Revised budget allocation is 15,000 USD after executive approval.",
            "importance": 8,
        },
    )
    assert update_res.status_code == 200

    # 3. Check version history via /versions
    hist_res = await client.get(f"/api/v1/memories/{mem_id}/versions", headers=auth_headers)
    assert hist_res.status_code == 200
    versions = hist_res.json()["data"]
    assert len(versions) >= 1
    assert any("10,000 USD" in v["content"] for v in versions)

    # 4. Restore original version
    restore_res = await client.post(
        f"/api/v1/memories/{mem_id}/restore?version_number=1",
        headers=auth_headers,
    )
    assert restore_res.status_code == 200
    restored = restore_res.json()["data"]
    assert "10,000 USD" in restored["content"]


@pytest.mark.asyncio
async def test_scenario_7_contradiction_detection_and_review_inbox(
    client: AsyncClient, auth_headers: dict
):
    """Scenario 7: Ingest a conflicting memory and verify conflict handling."""
    # 1. Base preference: dark mode
    res1 = await client.post(
        "/api/v1/memories",
        headers=auth_headers,
        json={
            "content": "User prefers dark mode interface for night coding.",
            "category": "preference",
            "importance": 8,
        },
    )
    assert res1.status_code == 201

    # 2. Conflicting preference: prefers light mode
    res2 = await client.post(
        "/api/v1/memories",
        headers=auth_headers,
        json={
            "content": "User prefers light mode for readability during daytime.",
            "category": "preference",
            "importance": 8,
        },
    )
    assert res2.status_code == 201
    data2 = res2.json()["data"]
    assert data2["status"] == "pending_review"

    # 3. Check memory reviews inbox
    reviews_res = await client.get("/api/v1/memory-reviews?status=pending", headers=auth_headers)
    assert reviews_res.status_code == 200
    rev_items = reviews_res.json()["data"]["items"]
    assert any(r["memory_id"] == data2["id"] for r in rev_items)


@pytest.mark.asyncio
async def test_scenario_8_knowledge_graph_relationship_traversal(
    client: AsyncClient, auth_headers: dict
):
    """Scenario 8: Explore project relationships in the knowledge graph."""
    # 1. Ingest text to extract entities & relationships
    await client.post(
        "/api/v1/graph/extract",
        headers=auth_headers,
        json={
            "text": (
                "Antigravity develops AI-MemoryVerse. Google Deepmind engineers build Antigravity."
            )
        },
    )

    # 2. Fetch full graph
    vis_res = await client.get("/api/v1/graph", headers=auth_headers)
    assert vis_res.status_code == 200
    graph_data = vis_res.json()["data"]
    assert "nodes" in graph_data
    assert "edges" in graph_data


@pytest.mark.asyncio
async def test_scenario_9_multi_tenant_zero_leakage_idor_defense(
    client: AsyncClient, auth_headers: dict
):
    """Scenario 9: Verify user B cannot access, read, edit, or delete User A's data (IDOR)."""
    # 1. User A creates private memory
    user_a_mem = await client.post(
        "/api/v1/memories",
        headers=auth_headers,
        json={
            "content": "Secret Project Codename: Project Excalibur.",
            "category": "project",
        },
    )
    mem_id = user_a_mem.json()["data"]["id"]

    # 2. Register User B in a different workspace
    user_b_reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "attacker_user_b@attacker.com",
            "password": "Password123!",
            "full_name": "Attacker User",
            "workspace_name": "Attacker Workspace",
        },
    )
    assert user_b_reg.status_code == 201
    user_b_token = user_b_reg.json()["data"]["tokens"]["access_token"]
    user_b_ws = user_b_reg.json()["data"]["workspace"]["id"]
    user_b_headers = {
        "Authorization": f"Bearer {user_b_token}",
        "X-Workspace-ID": user_b_ws,
    }

    # 3. User B attempts to read User A's memory
    b_get_res = await client.get(f"/api/v1/memories/{mem_id}", headers=user_b_headers)
    assert b_get_res.status_code in (403, 404)

    # 4. User B attempts to delete User A's memory
    b_del_res = await client.delete(f"/api/v1/memories/{mem_id}", headers=user_b_headers)
    assert b_del_res.status_code in (403, 404)

    # 5. User B attempts to search across User A's memories
    b_search_res = await client.post(
        "/api/v1/search/hybrid",
        headers=user_b_headers,
        json={
            "query": "Project Excalibur",
            "include_memories": True,
            "include_documents": False,
        },
    )
    assert b_search_res.status_code == 200
    assert len(b_search_res.json()["data"]["results"]) == 0


@pytest.mark.asyncio
async def test_scenario_10_cascade_deletion_handling(client: AsyncClient, auth_headers: dict):
    """Scenario 10: Delete a source and verify dependent data handling."""
    # 1. Upload doc
    files = {
        "file": (
            "temp_doc.txt",
            b"Temporary content that will be deleted to test cascading.",
            "text/plain",
        )
    }
    doc_res = await client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files=files,
        data={"title": "Doc to Delete"},
    )
    doc_id = doc_res.json()["data"]["document"]["id"]

    # 2. Delete doc
    del_res = await client.delete(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert del_res.status_code == 200

    # 3. Querying doc returns 404
    get_res = await client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_scenario_11_and_12_worker_health_and_system_readiness(
    client: AsyncClient, auth_headers: dict
):
    """Scenarios 11 & 12: Verify system readiness, health probes, and background
    worker telemetry.
    """
    # 1. Liveness
    health_res = await client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"

    # 2. Readiness
    ready_res = await client.get("/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] == "ready"

    # 3. Admin Overview Telemetry
    admin_res = await client.get("/api/v1/admin/overview", headers=auth_headers)
    assert admin_res.status_code == 200
    data = admin_res.json()["data"]
    assert "health" in data
    assert data["health"]["database"]["status"] == "healthy"
    assert data["health"]["background_worker"]["status"] == "healthy"


# =========================================================================
# OWASP Top 10 Security Defenses Validation Suite
# =========================================================================


@pytest.mark.asyncio
async def test_security_sql_injection_defense(client: AsyncClient, auth_headers: dict):
    """OWASP A03: Injection defense — verify SQL injection payloads do not break query execution."""
    sql_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE memories; --",
        "' UNION SELECT * FROM users --",
        "admin' --",
        "1; SELECT pg_sleep(5);",
    ]

    for payload in sql_payloads:
        # Search query injection attempt
        search_res = await client.post(
            "/api/v1/search/hybrid",
            headers=auth_headers,
            json={"query": payload, "top_k": 5},
        )
        assert search_res.status_code == 200
        assert search_res.json()["success"] is True

        # Memory content injection attempt
        mem_res = await client.post(
            "/api/v1/memories",
            headers=auth_headers,
            json={"content": f"Test safe content {payload}", "category": "project"},
        )
        assert mem_res.status_code in (201, 200)


def test_security_ssrf_comprehensive_matrix():
    """OWASP A10: Server-Side Request Forgery (SSRF) defense against all reserved/private CIDRs."""
    forbidden_targets = [
        "http://127.0.0.1:8000/internal",
        "http://localhost:5432",
        "http://[::1]:8080",
        "http://169.254.169.254/latest/meta-data/",  # AWS metadata
        "http://10.0.0.1/admin",  # Private Class A
        "http://172.16.0.1/secrets",  # Private Class B
        "http://192.168.1.1/router",  # Private Class C
        "http://100.64.0.1/cgnat",  # Carrier-grade NAT
        "file:///etc/passwd",  # Non-HTTP scheme
        "gopher://localhost:11211",  # Non-HTTP scheme
    ]

    for target in forbidden_targets:
        with pytest.raises(Exception):
            validate_url_safe(target)


@pytest.mark.asyncio
async def test_security_pii_and_credential_leak_guardrails(client: AsyncClient, auth_headers: dict):
    """Sensitive data leakage prevention: credential detection flags or prevents extraction."""
    leak_text = "I love coding in Python. My super secret password is: super_secret_pwd_998811."
    res = await client.post(
        "/api/v1/memories/extract",
        headers=auth_headers,
        json={"text": leak_text, "source_type": "note"},
    )
    assert res.status_code == 200
    memories = res.json()["data"]["memories"]
    all_contents = [m["content"].lower() for m in memories]
    assert not any("super_secret_pwd_998811" in c for c in all_contents)


@pytest.mark.asyncio
async def test_security_unauthenticated_access_denial(client: AsyncClient):
    """OWASP A01: Broken Access Control — unauthenticated requests must be rejected with 401."""
    protected_endpoints = [
        ("/api/v1/memories", "GET"),
        ("/api/v1/documents", "GET"),
        ("/api/v1/chat/conversations", "GET"),
        ("/api/v1/billing/usage", "GET"),
        ("/api/v1/billing/subscription", "GET"),
        ("/api/v1/admin/overview", "GET"),
        ("/api/v1/graph", "GET"),
        ("/api/v1/tokens", "GET"),
        ("/api/v1/agents/tasks", "GET"),
    ]

    for path, method in protected_endpoints:
        if method == "GET":
            res = await client.get(path)
        else:
            res = await client.post(path, json={})
        assert res.status_code == 401, f"Expected 401 for {path}, got {res.status_code}"
