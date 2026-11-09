import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_gdpr_data_portability_export(client: AsyncClient):
    """Verify GDPR Article 20 machine-readable portable data bundle export."""
    # 1. Register user
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "gdpr_exporter@example.com",
            "password": "SecurePassword123!",
            "full_name": "GDPR Exporter",
        },
    )
    assert reg_res.status_code == 201
    token = reg_res.json()["data"]["tokens"]["access_token"]
    ws_id = reg_res.json()["data"]["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # 2. Create sample memory
    mem_res = await client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "content": "User preferences and security configurations.",
            "category": "preference",
            "tags": ["personal", "gdpr"],
        },
    )
    assert mem_res.status_code == 201

    # 3. Upload sample document
    files = {"file": ("test_doc.txt", io.BytesIO(b"Document content for GDPR test"), "text/plain")}
    doc_res = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id},
        files=files,
    )
    assert doc_res.status_code == 201

    # 4. Create chat conversation & message
    conv_res = await client.post(
        "/api/v1/chat/conversations",
        headers=headers,
        json={"title": "GDPR Conversation"},
    )
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["data"]["id"]

    await client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        headers=headers,
        json={"content": "Hello GDPR vault"},
    )

    # 5. Fetch GDPR Article 20 portable export
    export_res = await client.get("/api/v1/users/me/export", headers=headers)
    assert export_res.status_code == 200
    export_data = export_res.json()["data"]

    # Verify all sections exist and are populated
    assert export_data["account"]["email"] == "gdpr_exporter@example.com"
    assert len(export_data["workspaces"]) >= 1
    assert any(
        "User preferences and security configurations." in m["content"]
        for m in export_data["memories"]
    )
    assert any(d["filename"] == "test_doc.txt" for d in export_data["documents"])
    assert any(c["title"] == "GDPR Conversation" for c in export_data["conversations"])
    assert len(export_data["sessions"]) >= 1

    # Verify integrity signature
    assert "integrity_sha256" in export_data["metadata"]
    assert len(export_data["metadata"]["integrity_sha256"]) == 64
    assert "GDPR Article 20" in export_data["metadata"]["compliance_standard"]


@pytest.mark.asyncio
async def test_gdpr_complete_account_erasure_cascade(client: AsyncClient):
    """Verify GDPR Article 17 Right to Erasure cascade cleanup."""
    # Register user
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "gdpr_erasure@example.com",
            "password": "SecurePassword123!",
            "full_name": "GDPR Erasure",
        },
    )
    token = reg_res.json()["data"]["tokens"]["access_token"]
    ws_id = reg_res.json()["data"]["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # Create memory
    await client.post(
        "/api/v1/memories",
        headers=headers,
        json={"content": "To be purged.", "category": "project"},
    )

    # Perform GDPR account deletion
    del_res = await client.delete("/api/v1/users/me", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Subsequent API call using revoked/deleted account token must fail
    followup_res = await client.get("/api/v1/auth/me", headers=headers)
    assert followup_res.status_code == 401


@pytest.mark.asyncio
async def test_api_token_scope_enforcement_allowed(client: AsyncClient):
    """Verify programmatic API token executes actions granted by its scopes."""
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "scoped_token_user@example.com",
            "password": "SecurePassword123!",
            "full_name": "Scoped Token User",
        },
    )
    token = reg_res.json()["data"]["tokens"]["access_token"]
    ws_id = reg_res.json()["data"]["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # Create programmatic API token with memories:read and search scopes
    create_res = await client.post(
        "/api/v1/tokens",
        headers=headers,
        json={
            "name": "Read Only Scoped Token",
            "scopes": ["memories:read", "search"],
        },
    )
    assert create_res.status_code == 201
    raw_api_token = create_res.json()["data"]["token"]
    api_token_headers = {"Authorization": f"Bearer {raw_api_token}", "X-Workspace-ID": ws_id}

    # memories:read scope is present -> GET /memories succeeds
    list_res = await client.get("/api/v1/memories", headers=api_token_headers)
    assert list_res.status_code == 200

    # search scope is present -> POST /search/hybrid succeeds
    search_res = await client.post(
        "/api/v1/search/hybrid",
        headers=api_token_headers,
        json={"query": "test query"},
    )
    assert search_res.status_code == 200


@pytest.mark.asyncio
async def test_api_token_scope_enforcement_rejected(client: AsyncClient):
    """Verify programmatic API token is blocked (403) from operations outside its granted scopes."""
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "restricted_token_user@example.com",
            "password": "SecurePassword123!",
            "full_name": "Restricted Token User",
        },
    )
    token = reg_res.json()["data"]["tokens"]["access_token"]
    ws_id = reg_res.json()["data"]["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # Token with strictly memories:read scope
    create_res = await client.post(
        "/api/v1/tokens",
        headers=headers,
        json={
            "name": "Read-Only Token",
            "scopes": ["memories:read"],
        },
    )
    assert create_res.status_code == 201
    raw_api_token = create_res.json()["data"]["token"]
    api_token_headers = {"Authorization": f"Bearer {raw_api_token}", "X-Workspace-ID": ws_id}

    # 1. Attempt POST /memories (requires memories:write) -> 403 Forbidden
    mem_res = await client.post(
        "/api/v1/memories",
        headers=api_token_headers,
        json={"content": "Should fail.", "category": "project"},
    )
    assert mem_res.status_code == 403
    assert "memories:write" in mem_res.json()["error"]["message"]

    # 2. Attempt POST /documents/upload (requires documents:write) -> 403 Forbidden
    files = {"file": ("test.txt", io.BytesIO(b"Blocked upload"), "text/plain")}
    doc_res = await client.post(
        "/api/v1/documents/upload",
        headers=api_token_headers,
        files=files,
    )
    assert doc_res.status_code == 403
    assert "documents:write" in doc_res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_admin_compliance_audit_log_export(client: AsyncClient):
    """Verify compliance audit log export in JSON and CSV formats."""
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "audit_admin@example.com",
            "password": "SecurePassword123!",
            "full_name": "Audit Admin",
        },
    )
    token = reg_res.json()["data"]["tokens"]["access_token"]
    ws_id = reg_res.json()["data"]["workspace"]["id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-ID": ws_id}

    # Trigger action to create an audit event
    await client.post(
        "/api/v1/tokens",
        headers=headers,
        json={"name": "Audit Test Token", "scopes": ["memories:read"]},
    )

    # 1. JSON Export
    json_export = await client.get("/api/v1/admin/audit-logs/export?format=json", headers=headers)
    assert json_export.status_code == 200
    json_data = json_export.json()["data"]
    assert "workspace_id" in json_data
    assert "events" in json_data
    assert "integrity_sha256" in json_data
    assert len(json_data["integrity_sha256"]) == 64

    # 2. CSV Export
    csv_export = await client.get("/api/v1/admin/audit-logs/export?format=csv", headers=headers)
    assert csv_export.status_code == 200
    assert "text/csv" in csv_export.headers.get("content-type", "")
    assert "id,workspace_id,user_id,action,ip_address,created_at" in csv_export.text
