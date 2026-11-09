import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.ai.semantic_cache import SemanticCache
from app.core.encryption import SecretEncryptionService


@pytest.fixture(autouse=True)
def clean_cache():
    SemanticCache.clear()
    yield
    SemanticCache.clear()


@pytest.mark.asyncio
async def test_workspace_ip_allowlist_enforcement(client: AsyncClient):
    """Verify workspace IP allowlist CIDR geofencing blocks unauthorized networks and permits allowed ones."""
    # 1. Register user
    email = f"ip_test_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "IP Policy User"},
    )
    assert reg.status_code == 201
    token = reg.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get default workspace
    ws_res = await client.get("/api/v1/workspaces", headers=headers)
    assert ws_res.status_code == 200
    workspace_id = ws_res.json()["data"][0]["id"]
    ws_headers = {**headers, "X-Workspace-ID": workspace_id}

    # 3. Initially without IP policy, requests from any IP succeed
    mem_init = await client.get("/api/v1/memories", headers=ws_headers)
    assert mem_init.status_code == 200

    # 4. Attempt to configure malformed CIDR rule -> 422 Unprocessable Entity
    bad_rule_res = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/ip-policy",
        json={"ip_allowlist": ["999.999.999.999/99"]},
        headers=headers,
    )
    assert bad_rule_res.status_code == 422

    # 5. Configure valid IP allowlist: corporate subnet and specific office IP
    valid_rules = ["192.168.1.0/24", "10.0.0.1/32"]
    policy_res = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/ip-policy",
        json={"ip_allowlist": valid_rules},
        headers=headers,
    )
    assert policy_res.status_code == 200
    assert policy_res.json()["data"]["settings"]["ip_allowlist"] == valid_rules

    # 6. Request from allowed corporate subnet (192.168.1.50) -> 200 OK
    allowed_headers_1 = {**ws_headers, "X-Forwarded-For": "192.168.1.50"}
    res_allowed_1 = await client.get("/api/v1/memories", headers=allowed_headers_1)
    assert res_allowed_1.status_code == 200

    # 7. Request from allowed specific host IP (10.0.0.1) -> 200 OK
    allowed_headers_2 = {**ws_headers, "X-Forwarded-For": "10.0.0.1"}
    res_allowed_2 = await client.get("/api/v1/memories", headers=allowed_headers_2)
    assert res_allowed_2.status_code == 200

    # 8. Request from untrusted external IP (203.0.113.195) -> 403 Forbidden
    blocked_headers = {**ws_headers, "X-Forwarded-For": "203.0.113.195"}
    res_blocked = await client.get("/api/v1/memories", headers=blocked_headers)
    assert res_blocked.status_code == 403
    error_msg = res_blocked.json().get("error", {}).get("message", "")
    assert "not permitted by workspace IP security policy" in error_msg

    # 9. Clear allowlist -> access restored for all
    clear_res = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/ip-policy",
        json={"ip_allowlist": []},
        headers=headers,
    )
    assert clear_res.status_code == 200
    res_open = await client.get("/api/v1/memories", headers=blocked_headers)
    assert res_open.status_code == 200


@pytest.mark.asyncio
async def test_workspace_envelope_secrets_encryption_at_rest(client: AsyncClient):
    """Verify secrets are encrypted with Fernet at rest, masked in API output, and decryptable."""
    email = f"secrets_test_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "Secrets User"},
    )
    token = reg.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ws_res = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = ws_res.json()["data"][0]["id"]

    secret_name = "OPENAI_API_KEY"
    secret_value = "sk-proj-super-confidential-api-token-9876543210"

    # 1. Store secret
    store_res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/secrets",
        json={"name": secret_name, "value": secret_value},
        headers=headers,
    )
    assert store_res.status_code == 201
    data = store_res.json()["data"]
    assert data["name"] == secret_name
    assert data["masked_value"] == SecretEncryptionService.mask_secret(secret_value)
    assert secret_value not in data["masked_value"]

    # 2. Verify encrypted representation in workspace settings
    ws_detail = await client.get(f"/api/v1/workspaces/{workspace_id}", headers=headers)
    encrypted_secrets = ws_detail.json()["data"]["settings"]["encrypted_secrets"]
    assert secret_name in encrypted_secrets
    raw_ciphertext = encrypted_secrets[secret_name]["ciphertext"]
    assert secret_value not in raw_ciphertext  # Plaintext never persisted directly

    # 3. Cryptographically decrypt ciphertext to verify integrity
    decrypted = SecretEncryptionService.decrypt_secret(raw_ciphertext)
    assert decrypted == secret_value

    # 4. List secrets via API -> returns masked values
    list_res = await client.get(f"/api/v1/workspaces/{workspace_id}/secrets", headers=headers)
    assert list_res.status_code == 200
    secrets_list = list_res.json()["data"]
    assert len(secrets_list) == 1
    assert secrets_list[0]["name"] == secret_name
    assert secrets_list[0]["masked_value"] == "sk-p••••3210"

    # 5. Delete secret
    del_res = await client.delete(
        f"/api/v1/workspaces/{workspace_id}/secrets/{secret_name}",
        headers=headers,
    )
    assert del_res.status_code == 200
    assert del_res.json()["data"]["deleted"] is True

    # 6. Verify secret is gone
    list_res_after = await client.get(f"/api/v1/workspaces/{workspace_id}/secrets", headers=headers)
    assert len(list_res_after.json()["data"]) == 0


@pytest.mark.asyncio
async def test_automated_memory_redundancy_deduplication(client: AsyncClient):
    """Verify automated memory redundancy deduplication merges redundant memories and marks duplicates SUPERSEDED."""
    email = f"dedup_test_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "Dedup User"},
    )
    token = reg.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ws_res = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = ws_res.json()["data"][0]["id"]
    ws_headers = {**headers, "X-Workspace-ID": workspace_id}

    # 1. Create two redundant memories with slight phrasing variations (~83% token similarity)
    content1 = (
        "The engineering team prefers React and TypeScript for all frontend interface engineering"
    )
    content2 = "The engineering team prefers React and TypeScript for modern frontend interface engineering"

    mem1_res = await client.post(
        "/api/v1/memories",
        json={"content": content1, "category": "preference", "tags": ["frontend", "react"]},
        headers=ws_headers,
    )
    assert mem1_res.status_code == 201
    mem1_id = mem1_res.json()["data"]["id"]

    mem2_res = await client.post(
        "/api/v1/memories",
        json={
            "content": content2,
            "category": "preference",
            "tags": ["frontend", "typescript"],
        },
        headers=ws_headers,
    )
    assert mem2_res.status_code == 201
    mem2_id = mem2_res.json()["data"]["id"]
    assert mem2_id != mem1_id  # Both created as distinct records

    # 3. Create a third distinct memory
    mem3_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "PostgreSQL with pgvector is configured for vector embeddings and search.",
            "category": "semantic",
            "tags": ["database"],
        },
        headers=ws_headers,
    )
    assert mem3_res.status_code == 201
    mem3_id = mem3_res.json()["data"]["id"]

    # 4. Trigger deduplication engine with threshold 0.80
    dedup_res = await client.post(
        "/api/v1/memories/deduplicate",
        json={"similarity_threshold": 0.80, "auto_merge": True},
        headers=ws_headers,
    )
    assert dedup_res.status_code == 200
    dedup_data = dedup_res.json()["data"]
    assert dedup_data["scanned_count"] >= 3
    assert dedup_data["duplicates_found"] == 1
    assert dedup_data["consolidated_count"] == 1

    detail = dedup_data["details"][0]
    assert detail["primary_id"] == mem1_id
    assert detail["duplicate_id"] == mem2_id
    assert detail["similarity"] >= 0.80
    assert detail["action"] == "superseded"

    # 5. Verify memory states
    # Primary memory (mem1) remains APPROVED and has merged tags
    get_m1 = await client.get(f"/api/v1/memories/{mem1_id}", headers=ws_headers)
    assert get_m1.status_code == 200
    m1_tags = get_m1.json()["data"]["tags"]
    assert "react" in m1_tags
    assert "typescript" in m1_tags

    # Duplicate memory (mem2) is SUPERSEDED and points to mem1
    get_m2 = await client.get(f"/api/v1/memories/{mem2_id}", headers=ws_headers)
    assert get_m2.status_code == 200
    assert get_m2.json()["data"]["status"] == "superseded"
    assert get_m2.json()["data"]["superseded_by"] == mem1_id

    # Distinct memory (mem3) remains APPROVED
    get_m3 = await client.get(f"/api/v1/memories/{mem3_id}", headers=ws_headers)
    assert get_m3.status_code == 200
    assert get_m3.json()["data"]["status"] == "approved"


@pytest.mark.asyncio
async def test_workspace_data_retention_and_ttl_pruning(client: AsyncClient):
    """Verify retention policy and valid_until TTL pruning archives expired memories while protecting pinned records."""
    email = f"retention_test_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "Retention User"},
    )
    token = reg.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ws_res = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = ws_res.json()["data"][0]["id"]
    ws_headers = {**headers, "X-Workspace-ID": workspace_id}

    # 1. Set retention policy to 30 days
    ret_res = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/retention-policy",
        json={"retention_days": 30},
        headers=headers,
    )
    assert ret_res.status_code == 200
    assert ret_res.json()["data"]["settings"]["retention_days"] == 30

    # 2. Create memory with expired valid_until (past TTL)
    now = datetime.now(UTC)
    expired_ttl = (now - timedelta(days=2)).isoformat()
    m_ttl = await client.post(
        "/api/v1/memories",
        json={
            "content": "Temporary ephemeral deployment note",
            "category": "episodic",
            "valid_until": expired_ttl,
        },
        headers=ws_headers,
    )
    assert m_ttl.status_code == 201
    m_ttl_id = m_ttl.json()["data"]["id"]

    # 3. Create active fresh memory
    m_fresh = await client.post(
        "/api/v1/memories",
        json={
            "content": "Core architecture decision for active memory retention",
            "category": "semantic",
        },
        headers=ws_headers,
    )
    assert m_fresh.status_code == 201
    m_fresh_id = m_fresh.json()["data"]["id"]

    # 4. Create pinned memory with expired TTL (pinned memories MUST be protected from pruning)
    m_pinned = await client.post(
        "/api/v1/memories",
        json={
            "content": "Pinned corporate principle never to be pruned",
            "category": "semantic",
            "is_pinned": True,
            "valid_until": expired_ttl,
        },
        headers=ws_headers,
    )
    assert m_pinned.status_code == 201
    m_pinned_id = m_pinned.json()["data"]["id"]

    # 5. Execute retention pruning
    prune_res = await client.post(
        f"/api/v1/workspaces/{workspace_id}/retention/prune",
        headers=headers,
    )
    assert prune_res.status_code == 200
    prune_data = prune_res.json()["data"]
    assert prune_data["pruned_count"] >= 1
    assert m_ttl_id in prune_data["archived_ids"]
    assert m_pinned_id not in prune_data["archived_ids"]
    assert m_fresh_id not in prune_data["archived_ids"]

    # 6. Verify status in database
    get_ttl = await client.get(f"/api/v1/memories/{m_ttl_id}", headers=ws_headers)
    assert get_ttl.json()["data"]["status"] == "archived"

    get_pinned = await client.get(f"/api/v1/memories/{m_pinned_id}", headers=ws_headers)
    assert get_pinned.json()["data"]["status"] == "approved"

    get_fresh = await client.get(f"/api/v1/memories/{m_fresh_id}", headers=ws_headers)
    assert get_fresh.json()["data"]["status"] == "approved"


@pytest.mark.asyncio
async def test_workspace_security_rbac_guards(client: AsyncClient):
    """Verify non-admin workspace members cannot modify IP policy, manage secrets, or prune data."""
    # 1. Create owner user
    owner_reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"owner_{uuid.uuid4().hex[:6]}@example.com",
            "password": "SecurePassword123!",
            "full_name": "Workspace Owner",
        },
    )
    owner_token = owner_reg.json()["data"]["tokens"]["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    ws_res = await client.get("/api/v1/workspaces", headers=owner_headers)
    workspace_id = ws_res.json()["data"][0]["id"]

    # 2. Create second user (member)
    member_email = f"viewer_{uuid.uuid4().hex[:6]}@example.com"
    member_reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": member_email,
            "password": "SecurePassword123!",
            "full_name": "Workspace Member",
        },
    )
    member_token = member_reg.json()["data"]["tokens"]["access_token"]
    member_user_id = member_reg.json()["data"]["user"]["id"]
    member_headers = {"Authorization": f"Bearer {member_token}"}

    # 3. Add second user as VIEWER to workspace
    add_member = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"user_id": member_user_id, "role": "viewer"},
        headers=owner_headers,
    )
    assert add_member.status_code == 201

    # 4. Viewer attempts to update IP policy -> 403 Forbidden
    ip_forbidden = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/ip-policy",
        json={"ip_allowlist": ["10.0.0.0/8"]},
        headers=member_headers,
    )
    assert ip_forbidden.status_code == 403

    # 5. Viewer attempts to store secret -> 403 Forbidden
    secret_forbidden = await client.post(
        f"/api/v1/workspaces/{workspace_id}/secrets",
        json={"name": "HACK_KEY", "value": "unauthorized-value"},
        headers=member_headers,
    )
    assert secret_forbidden.status_code == 403

    # 6. Viewer attempts to prune retention memories -> 403 Forbidden
    prune_forbidden = await client.post(
        f"/api/v1/workspaces/{workspace_id}/retention/prune",
        headers=member_headers,
    )
    assert prune_forbidden.status_code == 403
